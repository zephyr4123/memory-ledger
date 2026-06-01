// 发起一轮对话并解析 SSE 流:
//   reply_delta  实时回复 token
//   tool_call    小本开始调某把工具 (name + 解析好的 args) —— 让用户看见它真在查
//   tool_result  那把工具有了结果 (ok 与否)
//   done         终态 (闸门 / 真相 / 账本)
import type { ToolEvent, TurnDone } from "./types";

interface TurnHandlers {
  onDelta: (text: string) => void;
  onToolCall: (ev: { id: string; name: string; args?: Record<string, unknown> }) => void;
  onToolResult: (ev: { id: string; ok: boolean }) => void;
  onDone: (done: TurnDone) => void;
}

function parseBlock(block: string): { event: string; data: unknown } | null {
  let event = "message";
  const dataLines: string[] = [];
  for (const line of block.split("\n")) {
    if (line.startsWith("event:")) event = line.slice(6).trim();
    else if (line.startsWith("data:")) dataLines.push(line.slice(5).trim());
  }
  if (dataLines.length === 0) return null;
  try {
    return { event, data: JSON.parse(dataLines.join("\n")) };
  } catch {
    return null;
  }
}

export async function streamTurn(
  utterance: string,
  conversationId: number,
  personId: number | null,
  handlers: TurnHandlers,
  signal?: AbortSignal,
): Promise<void> {
  const res = await fetch("/api/turns", {
    method: "POST",
    headers: { "content-type": "application/json" },
    body: JSON.stringify({
      utterance,
      conversation_id: conversationId,
      person_id: personId ?? undefined,
    }),
    signal,
  });
  if (!res.ok || !res.body) {
    throw new Error(`turn failed: ${res.status}`);
  }

  const reader = res.body.getReader();
  const decoder = new TextDecoder();
  let buffer = "";

  for (;;) {
    const { done, value } = await reader.read();
    if (done) break;
    buffer += decoder.decode(value, { stream: true });

    let idx: number;
    while ((idx = buffer.indexOf("\n\n")) >= 0) {
      const block = buffer.slice(0, idx);
      buffer = buffer.slice(idx + 2);
      const parsed = parseBlock(block);
      if (!parsed) continue;
      if (parsed.event === "reply_delta") {
        handlers.onDelta((parsed.data as { text: string }).text);
      } else if (parsed.event === "tool_call") {
        handlers.onToolCall(parsed.data as Pick<ToolEvent, "id" | "name" | "args">);
      } else if (parsed.event === "tool_result") {
        handlers.onToolResult(parsed.data as { id: string; ok: boolean });
      } else if (parsed.event === "done") {
        handlers.onDone(parsed.data as TurnDone);
      }
    }
  }
}
