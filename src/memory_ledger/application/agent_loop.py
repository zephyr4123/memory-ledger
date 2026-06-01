"""AgentLoop —— 可复用的单轮对话编排 (application 层).

把"一轮 chat"的固定时序固化成一个 fold, 构造时注入 (MemoryLedger, Responder,
snapshot_builder). 只依赖 application + ports + domain, **绝不 import infrastructure**
—— 它是编排, 不是组合根 (具体 ledger/responder 由调用方在组合根装配后注入).

一轮时序 (对应 docs/01-design.md §9 的端到端流程):
  1. SNAPSHOT  —— 取本轮注入模型的上下文 (经 ledger.snapshot 缓存). 关键: 它**不含**
                  本轮稍后才写的 intent (snapshot 在请求开始时取, 下一轮才看到本轮的写).
  2. RESPOND   —— responder.respond(utterance, snapshot, turn) → Response (reply + intents).
  3. WRITE     —— 每条 ProposedIntent 走 ledger.write_intent (内部 normalize/validate/
                  auto-apply), 返回 WriteResult. 低危 ASSERT/ANNOTATE/FLAG 直接 APPLIED;
                  高危 PATCH 落 PROPOSED.
  4. BANNER    —— banner 与否**只看 WriteResult.needs_confirmation** (新建的、未 auto-apply
                  的 PATCH), 不重算策略 —— 故 (a) 低危 kind 即使 entity 不在矩阵也不会误报,
                  (b) 幂等重插 (created=False) 不重复 banner, (c) banner 显示 canonical 字段/值
                  与 DB 落库一致 (非 raw 别名). 真实 app 里用户点"采纳"→ 调 ledger.confirm.
  5. REPLY     —— 返回 reply + banner 列表.

cache invalidate 不是 loop 的独立步骤 —— 它是 ledger 写/确认转换的既定副作用
(write_intent auto-apply 后失效, confirm 后失效), loop 依赖它让下一轮 snapshot 新鲜.
"""

from __future__ import annotations

from collections.abc import Callable, Hashable
from dataclasses import dataclass

from ..domain.conversation import ProposedIntent, Response
from ..domain.intents.types import SourceLayer
from ..ports.responder import Responder
from .ledger import MemoryLedger

# snapshot_builder: (user_id) -> 纯函数, 构建注入模型的 snapshot 文本.
# 实体特定的拼装逻辑由它承载 (留在 example/调用方, 不进 application, 保持 application 实体无关).
SnapshotBuilder = Callable[[str], str]


@dataclass(frozen=True, slots=True)
class Banner:
    """一条待用户确认的高危改动 (PROPOSED PATCH). 字段值取 canonical (与 DB 一致)."""

    intent_id: int
    target_field: str | None
    proposed_value: object
    confidence: float


@dataclass(frozen=True, slots=True)
class TurnResult:
    """一轮的产物: 面向用户的 reply + 待确认 banner 列表."""

    reply: str
    banners: tuple[Banner, ...]


class AgentLoop:
    def __init__(
        self,
        ledger: MemoryLedger,
        responder: Responder,
        snapshot_builder: SnapshotBuilder,
        *,
        source_table: str = "chat_message",
        default_source_layer: SourceLayer = "L2_CHAT",
        patch_source_layer: SourceLayer = "AGENT_INFERENCE",
    ) -> None:
        self.ledger = ledger
        self.responder = responder
        self.snapshot_builder = snapshot_builder
        self.source_table = source_table
        self.default_source_layer = default_source_layer
        self.patch_source_layer = patch_source_layer

    def run_turn(
        self,
        user_id: str,
        utterance: str,
        turn: int,
        *,
        source_id: str,
        snapshot_scope: Hashable | None = None,
    ) -> TurnResult:
        """跑一轮. source_id 唯一标识本轮消息 (幂等 + 溯源反查的键)."""
        # 1. SNAPSHOT (本轮模型看到的上下文; 经缓存; 不含本轮稍后的写)
        scope = snapshot_scope if snapshot_scope is not None else turn
        snapshot = self.ledger.snapshot(
            user_id, scope, lambda: self.snapshot_builder(user_id)
        )

        # 2. RESPOND
        response: Response = self.responder.respond(
            utterance=utterance, snapshot=snapshot, turn=turn
        )

        # 3. WRITE + 4. BANNER
        banners: list[Banner] = []
        for pi in response.intents:
            banner = self._write_one(user_id, pi, source_id)
            if banner is not None:
                banners.append(banner)

        # 5. REPLY
        return TurnResult(reply=response.reply, banners=tuple(banners))

    def _write_one(
        self, user_id: str, pi: ProposedIntent, source_id: str
    ) -> Banner | None:
        """写一条 intent; 仅当它是一条新建的待确认 PATCH 时返回 Banner.

        banner 判定完全交给 ledger 返回的 WriteResult.needs_confirmation —— 不在这里
        重算策略, 因此既不会把低危 kind 误报成 banner, 也不会对幂等重插重复出 banner.
        """
        source_layer = (
            self.patch_source_layer if pi.kind == "PATCH" else self.default_source_layer
        )
        result = self.ledger.write_intent(
            user_id=user_id,
            kind=pi.kind,
            target_entity=pi.target_entity,
            patch_json=pi.patch_json,
            source_layer=source_layer,
            source_table=self.source_table,
            source_id=source_id,
            reason=pi.reason,
            target_row_id=pi.target_row_id,
            target_field=pi.target_field,
            source_quote=pi.source_quote,
            confidence=pi.confidence,
        )
        if not result.needs_confirmation:
            return None

        # 用 canonical 字段/值 (与 DB 落库一致, 非 raw 别名)
        return Banner(
            intent_id=result.intent_id,  # type: ignore[arg-type]  # needs_confirmation ⇒ created ⇒ 非 None
            target_field=result.target_field,
            proposed_value=result.proposed_value,
            confidence=pi.confidence,
        )
