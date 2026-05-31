"""PsycopgAdapter —— DBAdapter 端口的 psycopg3 参考实现 (驱动级)."""

from __future__ import annotations

from collections.abc import Iterator, Sequence
from contextlib import contextmanager, suppress
from typing import Any, cast

from ...ports.database import DBAdapter, Row


class PsycopgAdapter:
    """基于 psycopg3 的 DBAdapter 实现.

    用法::

        import psycopg
        from memory_ledger import MemoryLedger, open_postgres

        conn = psycopg.connect("postgresql://localhost/mydb")
        ledger = open_postgres(conn)   # 组合根帮你把 adapter→repository→ledger 接好

    线程/并发: 一个 psycopg 连接非线程安全. 高并发下每 worker 各持一个连接.
    """

    def __init__(self, conn: Any, *, autocommit: bool = True) -> None:
        self._conn = conn
        self._in_tx = False
        # 顶层默认 autocommit, 让单条写立即可见; 事务块内临时关掉.
        # suppress: 某些 fake conn 没有 autocommit 属性, 容忍.
        with suppress(Exception):
            if not self._in_tx:
                conn.autocommit = autocommit

    # -- internal -------------------------------------------------------
    def _dict_cursor(self) -> Any:
        # 延迟 import, 避免未装 psycopg 时 import 本模块即失败.
        from psycopg.rows import dict_row

        return self._conn.cursor(row_factory=dict_row)

    # -- DBAdapter ------------------------------------------------------
    def execute(self, sql: str, params: Sequence[Any] | None = None) -> None:
        with self._conn.cursor() as cur:
            cur.execute(sql, params)

    def fetchone(self, sql: str, params: Sequence[Any] | None = None) -> Row | None:
        with self._dict_cursor() as cur:
            cur.execute(sql, params)
            return cast("Row | None", cur.fetchone())

    def fetchall(self, sql: str, params: Sequence[Any] | None = None) -> list[Row]:
        with self._dict_cursor() as cur:
            cur.execute(sql, params)
            return [cast("Row", r) for r in cur.fetchall()]

    @contextmanager
    def transaction(self) -> Iterator[DBAdapter]:
        # psycopg 的 conn.transaction() 管 commit/rollback;
        # 事务块内需要非 autocommit 才能持有 advisory_xact_lock 到 commit.
        prev_autocommit = getattr(self._conn, "autocommit", True)
        with suppress(Exception):
            self._conn.autocommit = False
        try:
            with self._conn.transaction():
                inner = PsycopgAdapter.__new__(PsycopgAdapter)
                inner._conn = self._conn
                inner._in_tx = True
                yield inner
        finally:
            with suppress(Exception):
                self._conn.autocommit = prev_autocommit
