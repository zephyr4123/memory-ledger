"""persistence —— Postgres 持久化适配器集合 (实现 ports 里的抽象)."""

from __future__ import annotations

from .postgres_repository import PostgresIntentRepository
from .psycopg_adapter import PsycopgAdapter
from .schema import (
    CORE_MIGRATION,
    DEFAULT_MIGRATIONS,
    EXAMPLE_MIGRATION,
    apply_schema,
    bundled_sql,
)
from .serialization import to_jsonb

__all__ = [
    "CORE_MIGRATION",
    "DEFAULT_MIGRATIONS",
    "EXAMPLE_MIGRATION",
    "PostgresIntentRepository",
    "PsycopgAdapter",
    "apply_schema",
    "bundled_sql",
    "to_jsonb",
]
