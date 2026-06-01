"""LiteLLMResponder —— 库 Responder 端口的通用实现, 经 LiteLLM 接任意 provider.

LiteLLM 把所有 provider 统一成 OpenAI ChatCompletions 接口 (含 tools / 流式), 因此
换模型只是改 env (LLM_MODEL / LLM_API_KEY / LLM_BASE_URL), 代码零改动 —— DeepSeek /
OpenAI / 任意 OpenAI 兼容端点 / Anthropic 皆可。

两条用法:
  * respond(...)     非流式, 实现 Responder 端口 (供 AgentLoop / 测试复用)。
  * stream_turn(...) 流式, 供 chat 路由: 先连续吐回复 token, 末尾吐结构化 intent。
结构化产出走 tool-use (而非让模型手写 JSON 文本), 最稳。
"""

from __future__ import annotations

import json
from collections.abc import Iterator
from typing import Any

from memory_ledger import Response

from .prompts import TOOL, TOOL_NAME, build_system_prompt, tool_intents_to_proposed


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


class LiteLLMResponder:
    """用 LiteLLM 同步应答: 一句话 → reply + 4-kind intent (provider 无关)。"""

    def __init__(
        self,
        *,
        model: str,
        api_key: str,
        base_url: str | None = None,
        person_id: int | None = None,
        max_tokens: int = 2048,
    ) -> None:
        import litellm

        litellm.drop_params = True  # 跨 provider: 丢弃该家不支持的参数而非报错
        litellm.suppress_debug_info = True
        self._litellm = litellm
        self._model = model
        self._api_key = api_key
        self._base_url = base_url
        self._person_id = person_id
        self._max_tokens = max_tokens

    def _kwargs(self, snapshot: str, utterance: str) -> dict[str, Any]:
        kw: dict[str, Any] = {
            "model": self._model,
            "messages": [
                {"role": "system", "content": build_system_prompt(snapshot)},
                {"role": "user", "content": utterance},
            ],
            "tools": [TOOL],
            "tool_choice": "auto",
            "api_key": self._api_key,
            "max_tokens": self._max_tokens,
        }
        if self._base_url:
            kw["api_base"] = self._base_url
        return kw

    # ── Responder 端口 (非流式) ─────────────────────────────────────────
    def respond(self, *, utterance: str, snapshot: str, turn: int) -> Response:
        resp = self._litellm.completion(**self._kwargs(snapshot, utterance))
        msg = resp.choices[0].message
        reply = (getattr(msg, "content", None) or "").strip()
        raw = _intents_from_tool_calls(getattr(msg, "tool_calls", None))
        return Response(
            reply=reply,
            intents=tuple(tool_intents_to_proposed(raw, self._person_id)),
        )

    # ── 流式 (chat 路由用) ──────────────────────────────────────────────
    def stream_turn(
        self, *, utterance: str, snapshot: str, person_id: int
    ) -> Iterator[tuple[str, Any]]:
        """先连续 yield ('delta', text_chunk), 最后 yield ('intents', list[ProposedIntent])。

        OpenAI 流式里 tool_call 的 arguments 是分片到达的, 按 index 累积后再 json 解析。
        """
        args_by_index: dict[int, str] = {}
        names_by_index: dict[int, str] = {}

        for chunk in self._litellm.completion(**self._kwargs(snapshot, utterance), stream=True):
            choices = getattr(chunk, "choices", None)
            if not choices:
                continue
            delta = choices[0].delta
            content = getattr(delta, "content", None)
            if content:
                yield ("delta", content)
            for tc in getattr(delta, "tool_calls", None) or []:
                idx = tc.index if getattr(tc, "index", None) is not None else 0
                fn = getattr(tc, "function", None)
                if fn is None:
                    continue
                if getattr(fn, "name", None):
                    names_by_index[idx] = fn.name
                if getattr(fn, "arguments", None):
                    args_by_index[idx] = args_by_index.get(idx, "") + fn.arguments

        raw: list[Any] = []
        for idx, args in args_by_index.items():
            if names_by_index.get(idx) != TOOL_NAME:
                continue
            try:
                raw.extend(json.loads(args).get("intents", []))
            except (ValueError, AttributeError):
                continue
        yield ("intents", tool_intents_to_proposed(raw, person_id))
