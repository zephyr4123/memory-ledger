"""组合根 (composition root) —— 把各层接线成可用的 MemoryLedger.

这是唯一允许同时 import application 与 infrastructure 的地方: 它负责依赖注入
的"接线", 而不参与业务. 应用启动 / 库使用者从这里拿到装配好的门面.
"""

from __future__ import annotations

from typing import Any

from .application import MemoryLedger, SnapshotCache
from .domain.policies import AutoApplyPolicy
from .infrastructure.persistence import PostgresIntentRepository, PsycopgAdapter


def open_postgres(
    conn: Any,
    *,
    auto_apply: AutoApplyPolicy | None = None,
    field_aliases: dict[str, str] | None = None,
    value_aliases: dict[str, dict[str, str]] | None = None,
    cache: SnapshotCache | None = None,
    known_entities: set[str] | None = None,
) -> MemoryLedger:
    """便捷工厂: 用一个 psycopg 连接装配好 adapter → repository → ledger.

    用法::

        import psycopg
        from memory_ledger import open_postgres, AutoApplyPolicy

        conn = psycopg.connect(DSN, autocommit=True)
        ledger = open_postgres(conn, auto_apply=AutoApplyPolicy.low_risk_for(["todo_item"]))
    """
    repository = PostgresIntentRepository(PsycopgAdapter(conn))
    return MemoryLedger(
        repository,
        auto_apply=auto_apply,
        field_aliases=field_aliases,
        value_aliases=value_aliases,
        cache=cache,
        known_entities=known_entities,
    )
