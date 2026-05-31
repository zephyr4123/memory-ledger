"""MemoryLedger —— 应用层用例编排.

只依赖 domain (规范化 / 校验 / 风险策略) + ports (IntentRepository). **不含任何
SQL, 不 import infrastructure** —— 持久化机制全在 repository 端口后面.

一条写入用例的编排链:
  normalize (domain) → validate (domain) → auto-apply 决策 (domain policy)
  → repository.insert (port) → 按结果失效读模型缓存 (application)
"""

from __future__ import annotations

from collections.abc import Callable, Hashable, Sequence
from datetime import datetime
from typing import Any

from ..domain.intents import (
    IntentRecord,
    Kind,
    SourceLayer,
    normalize_intent,
    validate_intent_shape,
)
from ..domain.intents.validation import IntentShapeError
from ..domain.policies import AutoApplyPolicy
from ..ports.database import Row
from ..ports.repository import IntentRepository
from .caching import SnapshotCache


class MemoryLedger:
    """账本的对外用例门面. 持久化经 IntentRepository 端口注入 (依赖倒置)."""

    def __init__(
        self,
        repository: IntentRepository,
        *,
        auto_apply: AutoApplyPolicy | None = None,
        field_aliases: dict[str, str] | None = None,
        value_aliases: dict[str, dict[str, str]] | None = None,
        cache: SnapshotCache | None = None,
    ) -> None:
        self.repo = repository
        self.auto_apply = auto_apply or AutoApplyPolicy()
        self.field_aliases = field_aliases or {}
        self.value_aliases = value_aliases or {}
        self.cache = cache if cache is not None else SnapshotCache()

    # ── write path ──────────────────────────────────────────────────
    def insert_intent(
        self,
        *,
        user_id: str,
        kind: Kind,
        target_entity: str,
        patch_json: dict[str, Any],
        source_layer: SourceLayer,
        source_table: str,
        source_id: str,
        reason: str = "",
        target_date: str | None = None,
        target_row_id: str | None = None,
        target_field: str | None = None,
        source_quote: str | None = None,
        confidence: float = 1.0,
        extracted_by: str | None = None,
    ) -> int | None:
        """写一条 intent. 返回 intent id; shape 非法返回 None; 幂等命中返回既有 id.

        auto-apply 命中 → APPLIED (立即进 effective view); 否则 → PROPOSED (等 confirm).
        """
        normalized = normalize_intent(
            {
                "kind": kind,
                "target_entity": target_entity,
                "target_date": target_date,
                "target_row_id": target_row_id,
                "target_field": target_field,
                "patch_json": patch_json or {},
                "confidence": confidence,
            },
            field_aliases=self.field_aliases,
            value_aliases=self.value_aliases,
        )
        try:
            validate_intent_shape(normalized)
        except IntentShapeError:
            return None

        record = IntentRecord(
            user_id=user_id,
            kind=kind,
            target_entity=target_entity,
            patch_json=normalized["patch_json"],
            source_layer=source_layer,
            source_table=source_table,
            source_id=source_id,
            reason=reason,
            target_date=normalized.get("target_date"),
            target_row_id=normalized.get("target_row_id"),
            target_field=normalized.get("target_field"),
            source_quote=source_quote,
            confidence=confidence,
            extracted_by=extracted_by,
        )
        auto = self.auto_apply.should_auto_apply(record.policy_view())
        outcome = self.repo.insert(record, auto_apply=auto)
        if auto and outcome.created:
            self.cache.invalidate(user_id)
        return outcome.intent_id

    # ── lifecycle transitions ───────────────────────────────────────
    def confirm(self, user_id: str, intent_ids: Sequence[int]) -> int:
        """PROPOSED → APPLIED (用户在 banner 拍板采纳). 返回生效条数."""
        if not intent_ids:
            return 0
        n = self.repo.confirm(user_id, intent_ids)
        if n:
            self.cache.invalidate(user_id)
        return n

    def reject(self, user_id: str, intent_ids: Sequence[int], reason: str = "") -> int:
        """PROPOSED/APPLIED → REJECTED. 返回条数."""
        if not intent_ids:
            return 0
        n = self.repo.reject(user_id, intent_ids, reason)
        if n:
            self.cache.invalidate(user_id)
        return n

    def expire_before(
        self,
        cutoff: datetime,
        *,
        user_id: str | None = None,
        target_entity: str | None = None,
    ) -> int:
        """把 applied_at < cutoff 的 live intent 标 EXPIRED. 返回条数."""
        affected = self.repo.expire_before(
            cutoff, user_id=user_id, target_entity=target_entity
        )
        for uid in set(affected):
            self.cache.invalidate(uid)
        return len(affected)

    # ── read path ───────────────────────────────────────────────────
    def effective(
        self,
        entity: str,
        user_id: str,
        row_id: int | str,
        *,
        as_of: datetime | None = None,
    ) -> Row | None:
        """合成 entity 行截至某时点的真相 (as_of=None → 现在)."""
        return self.repo.effective(entity, user_id, row_id, as_of=as_of)

    def snapshot(
        self,
        user_id: str,
        scope: Hashable,
        build_fn: Callable[[], str],
        *,
        force_refresh: bool = False,
    ) -> str:
        """带缓存地构建 snapshot. build_fn 必须是纯函数 (只读 effective view)."""
        return self.cache.get(user_id, scope, build_fn, force_refresh=force_refresh)
