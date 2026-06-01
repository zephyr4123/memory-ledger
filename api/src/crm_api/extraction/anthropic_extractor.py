"""AnthropicExtractor —— 库 Extractor 端口的真 LLM 实现 (Claude).

两条用法:
  * extract(...)      非流式, 实现 Extractor 端口 (供 AgentLoop / 测试复用)。
  * stream_turn(...)  流式, 供 chat 路由: 先连续吐回复 token, 末尾吐结构化 intent。

结构化产出走 tool-use (而非让模型手写 JSON 文本), 由 SDK 校验形状, 最稳。
"""

from __future__ import annotations

from collections.abc import Iterator
from typing import Any

from memory_ledger import Extraction, ProposedIntent

from .prompts import TOOL, TOOL_NAME, build_system_prompt, tool_intents_to_proposed


class AnthropicExtractor:
    """用 Claude 把一句话抽成 reply + 4-kind intent。"""

    def __init__(
        self,
        *,
        api_key: str,
        model: str,
        person_id: int | None = None,
        max_tokens: int = 1024,
    ) -> None:
        from anthropic import Anthropic

        self._client = Anthropic(api_key=api_key)
        self._model = model
        self._person_id = person_id
        self._max_tokens = max_tokens

    # ── Extractor 端口 (非流式) ─────────────────────────────────────────
    def extract(self, *, utterance: str, snapshot: str, turn: int) -> Extraction:
        msg = self._client.messages.create(
            model=self._model,
            max_tokens=self._max_tokens,
            system=build_system_prompt(snapshot),
            tools=[TOOL],
            messages=[{"role": "user", "content": utterance}],
        )
        reply_parts: list[str] = []
        raw_intents: list[Any] = []
        for block in msg.content:
            if block.type == "text":
                reply_parts.append(block.text)
            elif block.type == "tool_use" and block.name == TOOL_NAME:
                raw_intents = (block.input or {}).get("intents", [])
        return Extraction(
            reply="".join(reply_parts).strip(),
            intents=tuple(tool_intents_to_proposed(raw_intents, self._person_id)),
        )

    # ── 流式 (chat 路由用) ──────────────────────────────────────────────
    def stream_turn(
        self, *, utterance: str, snapshot: str, person_id: int
    ) -> Iterator[tuple[str, Any]]:
        """先连续 yield ('delta', text_chunk), 最后 yield ('intents', list[ProposedIntent])。"""
        raw_intents: list[Any] = []
        with self._client.messages.stream(
            model=self._model,
            max_tokens=self._max_tokens,
            system=build_system_prompt(snapshot),
            tools=[TOOL],
            messages=[{"role": "user", "content": utterance}],
        ) as stream:
            for event in stream:
                if (
                    event.type == "content_block_delta"
                    and event.delta.type == "text_delta"
                ):
                    yield ("delta", event.delta.text)
            final = stream.get_final_message()
        for block in final.content:
            if block.type == "tool_use" and block.name == TOOL_NAME:
                raw_intents = (block.input or {}).get("intents", [])
        intents: list[ProposedIntent] = tool_intents_to_proposed(raw_intents, person_id)
        yield ("intents", intents)
