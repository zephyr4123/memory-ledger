// 发起一轮对话并解析 SSE 流 (reply_delta 实时回复 token + done 终态)。
import type { TurnDone } from "./types";

interface TurnHandlers {
  onDelta: (text: string) => void;
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
  personId: number,
  handlers: TurnHandlers,
  signal?: AbortSignal,
): Promise<void> {
  const res = await fetch("/api/turns", {
    method: "POST",
    headers: { "content-type": "application/json" },
    body: JSON.stringify({ utterance, person_id: personId }),
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
      } else if (parsed.event === "done") {
        handlers.onDone(parsed.data as TurnDone);
      }
    }
  }
}
