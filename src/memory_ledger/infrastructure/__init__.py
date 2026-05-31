"""infrastructure —— 实现 ports 的具体技术适配器 (Postgres / SQL / JSON).

依赖方向: infrastructure 实现 ports、可用 domain; application 绝不依赖它.
子包:
  * persistence — DBAdapter 驱动实现、IntentRepository 的 Postgres 实现、schema 引导
"""

from __future__ import annotations

from .persistence import (
    PostgresIntentRepository,
    PsycopgAdapter,
    apply_schema,
    bundled_sql,
)

__all__ = [
    "PostgresIntentRepository",
    "PsycopgAdapter",
    "apply_schema",
    "bundled_sql",
]
