"""MockResponder —— ports.responder.Responder 的确定性脚本实现.

按轮号从冻结的 TRANSCRIPT 取预烘焙 Response. 不调模型、无时钟、无随机 —— respond 是
(script, turn) 的纯总函数. snapshot 入参被接受 (签名与真实模型一致) 但忽略, 保证纯度.

真实模型适配器 (LiteLLMResponder: 调模型 + 解析 wire JSON → Response) 在 api/ 应用里
(crm_api.responder), 不在此实现 —— 示例发布包零模型依赖、CI 零 key.
"""

from __future__ import annotations

from collections.abc import Sequence

from memory_ledger.domain.conversation import Response

from .transcript import ScriptedTurn


class MockResponder:
    """实现 Responder 协议: respond(utterance, snapshot, turn) -> Response."""

    def __init__(self, script: Sequence[ScriptedTurn]) -> None:
        self._script = tuple(script)

    def respond(self, *, utterance: str, snapshot: str, turn: int) -> Response:
        st = self._script[turn]
        if st.utterance != utterance:
            raise AssertionError(
                f"transcript drift at turn {turn}: "
                f"{utterance!r} != scripted {st.utterance!r}"
            )
        return st.response  # snapshot 被忽略 → 纯函数
