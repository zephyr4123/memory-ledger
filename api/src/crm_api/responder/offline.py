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
    "（离线模式：尚未配置 LLM_API_KEY，小本暂时只能查看、无法记录。"
    "配置后即为真实大模型对话，小本将自行检索记忆、实时应答，"
    "并将涉及修改的内容停在确认环节，待你确认。）"
)


class OfflineResponder:
    def respond(self, *, utterance: str, snapshot: str, turn: int) -> Response:
        return Response(reply=_NOTICE, intents=())

    def stream_turn(
        self,
        *,
        utterance: str,
        ctx: ToolContext,
        history: list[dict[str, Any]] | None = None,
        thinking: bool = False,
    ) -> Iterator[tuple[str, Any]]:
        yield ("delta", _NOTICE)
        yield ("intents", [])
