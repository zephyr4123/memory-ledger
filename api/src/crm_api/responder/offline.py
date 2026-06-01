"""OfflineResponder —— 无 LLM_API_KEY 时的降级实现.

产品真身需要真 LLM(见 README): 这个降级只为保证"没配 key 也能起服务 / 跑 CI",
它不产生任何 intent, 只回一句提示。/api/health 会把当前模式报成 mock。
"""

from __future__ import annotations

from collections.abc import Iterator
from typing import Any

from memory_ledger import Response

from ..tools import ToolContext

_NOTICE = (
    "(离线模式: 未配置 LLM_API_KEY, 小本暂时只能看、不能记。"
    "配置 key 后即为真 LLM 对话, 小本会自己查记忆、实时回复, 并把改动停在确认闸门等你点头。)"
)


class OfflineResponder:
    def respond(self, *, utterance: str, snapshot: str, turn: int) -> Response:
        return Response(reply=_NOTICE, intents=())

    def stream_turn(self, *, utterance: str, ctx: ToolContext) -> Iterator[tuple[str, Any]]:
        yield ("delta", _NOTICE)
        yield ("intents", [])
