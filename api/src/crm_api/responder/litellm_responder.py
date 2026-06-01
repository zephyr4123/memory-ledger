"""LiteLLMResponder —— 经 LiteLLM 接任意 provider 的 responder。

* stream_turn(...)  产品主路径: **agent loop** —— 模型自主调读工具(list_contacts /
  get_contact / review_open_items)去查信息、调写工具暂存改动, 多轮直到给出回复;全程流式。
  信息不再 prefill 进 prompt, 由小本自己决定查什么(涌现)。
* respond(...)      legacy 单次路径(库 Responder 端口 / 非 agentic 复用): snapshot 注入 + 写工具。

换模型只改 env(LLM_MODEL / LLM_API_KEY / LLM_BASE_URL), 代码零改动。
"""

from __future__ import annotations

import json
from collections.abc import Iterator
from typing import Any

from memory_ledger import Response

from ..tools import ToolContext, dispatch, openai_schemas
from ..tools.contacts import TOOL_NAME
from .prompts import build_agent_system_prompt, build_system_prompt, tool_intents_to_proposed

_MAX_ROUNDS = 6  # agent 自主调工具的轮数上限 (防死循环)
_MAX_HISTORY = 20  # 回灌进 prompt 的历史消息条数上限 (控 token)


def _intents_from_tool_calls(tool_calls: Any) -> list[Any]:
    raw: list[Any] = []
    for tc in tool_calls or []:
        fn = getattr(tc, "function", None)
        if fn is None or getattr(fn, "name", None) != TOOL_NAME:
            continue
        try:
            raw.extend(json.loads(fn.arguments).get("intents", []))
        except (ValueError, AttributeError, TypeError):
            continue
    return raw


def _focus_line(ctx: ToolContext) -> str:
    try:
        eff = ctx.ledger.effective("person", ctx.user_id, ctx.focus_person_id)
    except Exception:  # noqa: BLE001 — 定位行拿不到不该挡住对话
        eff = None
    if not eff:
        return f"#{ctx.focus_person_id}(信息暂缺)"
    name = eff.get("full_name_eff") or "未命名"
    extra = " · ".join(x for x in [eff.get("role_eff"), eff.get("employer_eff")] if x)
    return f"#{ctx.focus_person_id} {name}" + (f"({extra})" if extra else "")


class LiteLLMResponder:
    def __init__(
        self,
        *,
        model: str,
        api_key: str,
        base_url: str | None = None,
        max_tokens: int = 2048,
        request_timeout: float = 60.0,
    ) -> None:
        import litellm

        litellm.drop_params = True
        litellm.suppress_debug_info = True
        self._litellm = litellm
        self._model = model
        self._api_key = api_key
        self._base_url = base_url
        self._max_tokens = max_tokens
        self._request_timeout = request_timeout

    def _kwargs(self, messages: list[dict[str, Any]], **extra: Any) -> dict[str, Any]:
        kw: dict[str, Any] = {
            "model": self._model,
            "messages": messages,
            "api_key": self._api_key,
            "max_tokens": self._max_tokens,
            "timeout": self._request_timeout,
            **extra,
        }
        if self._base_url:
            kw["api_base"] = self._base_url
        return kw

    # ── legacy 单次路径 (库 Responder 端口) ──────────────────────────────
    def respond(self, *, utterance: str, snapshot: str, turn: int) -> Response:
        messages = [
            {"role": "system", "content": build_system_prompt(snapshot)},
            {"role": "user", "content": utterance},
        ]
        resp = self._litellm.completion(
            **self._kwargs(messages, tools=openai_schemas([TOOL_NAME]), tool_choice="auto")
        )
        msg = resp.choices[0].message
        reply = (getattr(msg, "content", None) or "").strip()
        raw = _intents_from_tool_calls(getattr(msg, "tool_calls", None))
        return Response(reply=reply, intents=tuple(tool_intents_to_proposed(raw, None)))

    # ── 产品主路径: agent loop (流式 + 自主工具调用) ──────────────────────
    def stream_turn(
        self,
        *,
        utterance: str,
        ctx: ToolContext,
        history: list[dict[str, Any]] | None = None,
    ) -> Iterator[tuple[str, Any]]:
        """流式跑一轮对话。yield 的事件:
        ('delta', text)        —— 回复 token
        ('tool_call', {...})   —— 开始调某工具 (name + 解析好的 args), 供前端实时可视化
        ('tool_result', {...}) —— 该工具有了结果 (ok 与否)
        ('intents', [...])     —— 收尾: 本轮暂存的待写改动
        """
        messages: list[dict[str, Any]] = [
            {"role": "system", "content": build_agent_system_prompt(_focus_line(ctx))}
        ]
        for h in (history or [])[-_MAX_HISTORY:]:  # 同一线程内的上下文 → 真多轮
            text = (h.get("content") or "").strip()
            if text:
                role = "assistant" if h.get("role") == "agent" else "user"
                messages.append({"role": role, "content": text})
        messages.append({"role": "user", "content": utterance})

        tools = openai_schemas()
        answered = False

        for _ in range(_MAX_ROUNDS):
            content, calls = yield from self._stream_round(messages, tools, "auto")
            if not calls:  # 模型直接给了回复 → 这轮就是最终答复
                answered = True
                break
            # 把本轮 assistant(含 tool_calls)回灌, 供下一轮参考
            messages.append(
                {
                    "role": "assistant",
                    "content": content or None,
                    "tool_calls": [
                        {
                            "id": c["id"],
                            "type": "function",
                            "function": {"name": c["name"], "arguments": c["args"] or "{}"},
                        }
                        for c in calls
                    ],
                }
            )
            for c in calls:
                try:
                    args = json.loads(c["args"]) if c["args"].strip() else {}
                except ValueError:
                    args = {}
                yield ("tool_call", {"id": c["id"], "name": c["name"], "args": args})
                result = dispatch(c["name"], args, ctx)
                ok = not (isinstance(result, dict) and "error" in result)
                yield ("tool_result", {"id": c["id"], "name": c["name"], "ok": ok})
                messages.append(
                    {
                        "role": "tool",
                        "tool_call_id": c["id"],
                        "content": json.dumps(result, ensure_ascii=False, default=str),
                    }
                )

        if not answered:  # 到达轮数上限仍在调工具 → 强制要一句收尾回复
            yield from self._stream_round(messages, tools=None, tool_choice="none")

        yield ("intents", list(ctx.staged_intents))

    def _stream_round(
        self, messages: list[dict[str, Any]], tools: list[dict[str, Any]] | None, tool_choice: str
    ) -> Iterator[tuple[str, Any]]:
        """流式跑一轮: yield ('delta', text) 给用户; 返回 (拼好的 content, 工具调用列表)。

        作为子生成器被 `yield from` —— 它的 return 值就是 (content, calls)。
        """
        extra: dict[str, Any] = {"stream": True}
        if tools:
            extra["tools"] = tools
            extra["tool_choice"] = tool_choice
        parts: list[str] = []
        args_by_index: dict[int, str] = {}
        names_by_index: dict[int, str] = {}
        ids_by_index: dict[int, str] = {}

        for chunk in self._litellm.completion(**self._kwargs(messages, **extra)):
            choices = getattr(chunk, "choices", None)
            if not choices:
                continue
            delta = choices[0].delta
            text = getattr(delta, "content", None)
            if text:
                parts.append(text)
                yield ("delta", text)
            for tc in getattr(delta, "tool_calls", None) or []:
                idx = tc.index if getattr(tc, "index", None) is not None else 0
                if getattr(tc, "id", None):
                    ids_by_index[idx] = tc.id
                fn = getattr(tc, "function", None)
                if fn is None:
                    continue
                if getattr(fn, "name", None):
                    names_by_index[idx] = fn.name
                if getattr(fn, "arguments", None):
                    args_by_index[idx] = args_by_index.get(idx, "") + fn.arguments

        calls = [
            {"id": ids_by_index.get(i, f"call_{i}"), "name": names_by_index[i], "args": args_by_index.get(i, "")}
            for i in sorted(names_by_index)
        ]
        return "".join(parts), calls
