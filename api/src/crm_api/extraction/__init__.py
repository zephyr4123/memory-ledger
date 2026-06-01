"""extraction —— 真 LLM extractor (Anthropic) + 离线降级 + 工厂.

库定义 `Extractor` 端口 (LLM 无关); 真 LLM 实现住在这里 —— 库核心不背 anthropic 依赖。
"""

from __future__ import annotations

from collections.abc import Iterator
from typing import Any, Protocol, runtime_checkable

from ..config import Settings
from .anthropic_extractor import AnthropicExtractor
from .offline import OfflineExtractor


@runtime_checkable
class TurnExtractor(Protocol):
    """库 Extractor 端口 + 流式 stream_turn 的合体 (chat 路由要流式)。"""

    def extract(self, *, utterance: str, snapshot: str, turn: int) -> Any: ...

    def stream_turn(
        self, *, utterance: str, snapshot: str, person_id: int
    ) -> Iterator[tuple[str, Any]]: ...


def make_extractor(settings: Settings) -> TurnExtractor:
    """有 key → 真 LLM (live); 无 key → 离线降级 (mock)。"""
    if settings.llm_enabled:
        assert settings.anthropic_api_key is not None
        return AnthropicExtractor(api_key=settings.anthropic_api_key, model=settings.model)
    return OfflineExtractor()


__all__ = ["AnthropicExtractor", "OfflineExtractor", "TurnExtractor", "make_extractor"]
