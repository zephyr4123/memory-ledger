"""DBAdapter 端口 —— 驱动级抽象 (低层 SQL 执行器).

这是给"换数据库驱动"留的扩展缝: 默认 psycopg3, 你可以实现同一个 Protocol
来接 asyncpg / SQLAlchemy / Supabase. 约定:

  * 占位符统一用 ``%s``. 实现方负责适配到自己驱动的占位符风格.
  * fetchone 无结果返回 None; fetchall 无结果返回 [].
  * transaction() 是上下文管理器: 进入开启事务, 正常退出 commit, 异常 rollback.
    事务内的 execute/fetch 必须落在同一连接, 以保证 advisory lock / FOR UPDATE 语义.
"""

from __future__ import annotations

from collections.abc import Iterator, Sequence
from contextlib import contextmanager
from typing import Any, Protocol, runtime_checkable

# 一行结果: 列名 -> 值
Row = dict[str, Any]


@runtime_checkable
class DBAdapter(Protocol):
    """memory-ledger 需要的最小数据库执行接口."""

    def execute(self, sql: str, params: Sequence[Any] | None = None) -> None:
        """执行一条不关心返回行的语句 (INSERT/UPDATE/DDL)."""
        ...

    def fetchone(self, sql: str, params: Sequence[Any] | None = None) -> Row | None:
        """执行查询并返回第一行 (dict) 或 None."""
        ...

    def fetchall(self, sql: str, params: Sequence[Any] | None = None) -> list[Row]:
        """执行查询并返回所有行 (list[dict])."""
        ...

    @contextmanager
    def transaction(self) -> Iterator[DBAdapter]:
        """开启一个事务, yield 一个在该事务内执行的 adapter."""
        ...
