"""Schema bootstrap —— 读取包内 bundled SQL 迁移并 apply 到一个 DBAdapter.

建表是部署/基础设施职责, 不属于运行期账本操作, 所以从 application 层挪到这里.
生产环境应改用正式迁移工具 (alembic / sqitch — 见 roadmap), 本函数用于 dev /
测试 / 一键 init.
"""

from __future__ import annotations

import importlib.resources as resources
from collections.abc import Sequence

from ...ports.database import DBAdapter

CORE_MIGRATION = "001_core.sql"
EXAMPLE_MIGRATION = "002_example_todo.sql"
DEFAULT_MIGRATIONS: tuple[str, ...] = (CORE_MIGRATION, EXAMPLE_MIGRATION)

_SQL_PACKAGE = "memory_ledger.infrastructure.persistence.sql"


def bundled_sql(name: str) -> str:
    """读取包内 bundled SQL 文本 (e.g. '001_core.sql')."""
    return resources.files(_SQL_PACKAGE).joinpath(name).read_text(encoding="utf-8")


def apply_schema(db: DBAdapter, files: Sequence[str] = DEFAULT_MIGRATIONS) -> None:
    """按顺序 apply 给定迁移到 db. 默认核心层 + todo 示例 (在干净库上跑)."""
    for name in files:
        db.execute(bundled_sql(name))
