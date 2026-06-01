"""OfflineExtractor —— 无 ANTHROPIC_API_KEY 时的降级实现.

产品真身需要真 LLM(见 README): 这个降级只为保证"没配 key 也能起服务 / 跑 CI",
它不产生任何 intent, 只回一句提示。/api/health 会把当前模式报成 mock。
"""

from __future__ import annotations

from collections.abc import Iterator
from typing import Any

from memory_ledger import Extraction

_NOTICE = (
    "(离线模式: 未配置 ANTHROPIC_API_KEY, 记忆写入已禁用。"
    "配置 key 后即为真 LLM 对话, 会实时回复并产出待确认的结构化改动。)"
)


class OfflineExtractor:
    def extract(self, *, utterance: str, snapshot: str, turn: int) -> Extraction:
        return Extraction(reply=_NOTICE, intents=())

    def stream_turn(
        self, *, utterance: str, snapshot: str, person_id: int
    ) -> Iterator[tuple[str, Any]]:
        yield ("delta", _NOTICE)
        yield ("intents", [])
