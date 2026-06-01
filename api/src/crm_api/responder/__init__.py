"""responder —— 通用 LLM responder (经 LiteLLM) + 离线降级 + 工厂.

库定义 `Responder` 端口 (LLM 无关); 真 LLM 实现住在这里, 经 LiteLLM 接任意 provider
—— 库核心不背任何 LLM SDK 依赖。
"""

from __future__ import annotations

from collections.abc import Iterator
from typing import Any, Protocol, runtime_checkable

from ..config import Settings
from ..tools import ToolContext
from .litellm_responder import LiteLLMResponder
from .offline import OfflineResponder


@runtime_checkable
class TurnResponder(Protocol):
    """库 Responder 端口 + 流式 agent loop 的合体 (chat 路由要流式 + 自主工具调用)。"""

    def respond(self, *, utterance: str, snapshot: str, turn: int) -> Any: ...

    def stream_turn(
        self, *, utterance: str, ctx: ToolContext
    ) -> Iterator[tuple[str, Any]]: ...


def make_responder(settings: Settings) -> TurnResponder:
    """有 key → 真 LLM (live, 经 LiteLLM); 无 key → 离线降级 (mock)。"""
    if settings.llm_enabled:
        assert settings.llm_api_key is not None
        return LiteLLMResponder(
            model=settings.llm_model,
            api_key=settings.llm_api_key,
            base_url=settings.llm_base_url,
        )
    return OfflineResponder()


__all__ = ["LiteLLMResponder", "OfflineResponder", "TurnResponder", "make_responder"]
