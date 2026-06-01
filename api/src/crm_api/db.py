"""DB 接线 —— 连接池 + 幂等迁移 + per-request ledger 工厂.

一个 psycopg 连接非线程安全, 而 FastAPI 把 sync 端点放线程池跑 → 用连接池: 每个
请求借一条连接、装配一个 ledger、用完归还。SnapshotCache 因此是 per-request 的
(对 demo 足够; 正确性优先于缓存命中)。
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from memory_ledger import MemoryLedger, PsycopgAdapter, open_postgres
from memory_ledger.infrastructure.persistence.schema import CRM_MIGRATIONS, bundled_sql

from .policy import FIELD_ALIASES, VALUE_ALIASES, crm_auto_apply_policy

if TYPE_CHECKING:
    from psycopg_pool import ConnectionPool


def make_pool(database_url: str) -> ConnectionPool:
    """建连接池 (不在构造里 open, 由 lifespan 显式 open/close)。"""
    from psycopg_pool import ConnectionPool

    return ConnectionPool(
        database_url,
        min_size=1,
        max_size=8,
        kwargs={"autocommit": True},
        open=False,
    )


def ensure_schema(conn: Any) -> None:
    """幂等 apply CRM 迁移链 (001→004). 已建 person 表则跳过 —— 003 不可逆, 防半途重复。"""
    adapter = PsycopgAdapter(conn)
    already = adapter.fetchone("SELECT to_regclass('person') AS t")
    if already is None or already["t"] is None:
        for name in CRM_MIGRATIONS:
            adapter.execute(bundled_sql(name))


def ledger_for(conn: Any) -> MemoryLedger:
    """用一条连接装配好 CRM 口径的 MemoryLedger。"""
    return open_postgres(
        conn,
        auto_apply=crm_auto_apply_policy(),
        field_aliases=FIELD_ALIASES,
        value_aliases=VALUE_ALIASES,
    )
