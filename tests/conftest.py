"""共享 pytest fixtures + 集成测试自动跳过.

测试结构镜像源码分层:
  tests/unit/         无 I/O 纯单元 (毫秒级), 镜像 domain/ + application/
  tests/integration/  需 docker 起 Postgres, 走真 SQL

集成测试无需手动加 marker: 下方 pytest_collection_modifyitems 钩子会给
``tests/integration/`` 下的所有用例自动挂 skip(当 docker/testcontainers 缺失时).
"""

from __future__ import annotations

from collections.abc import Iterator

import pytest

try:
    import psycopg
    from testcontainers.postgres import PostgresContainer

    from memory_ledger import AutoApplyPolicy, PsycopgAdapter, apply_schema, open_postgres

    _DEPS_OK = True
    _IMPORT_ERR: Exception | None = None
except Exception as exc:
    _DEPS_OK = False
    _IMPORT_ERR = exc


def pytest_collection_modifyitems(items: list[pytest.Item]) -> None:
    """集成测试 (tests/integration/) 在依赖缺失时整体自动 skip."""
    if _DEPS_OK:
        return
    skip = pytest.mark.skip(reason=f"integration deps missing: {_IMPORT_ERR}")
    for item in items:
        if "/integration/" in item.nodeid or "\\integration\\" in item.nodeid:
            item.add_marker(skip)


# ── 集成 fixtures (仅集成测试用; 单元测试不触发容器启动) ──────────────
@pytest.fixture(scope="session")
def pg_dsn() -> Iterator[str]:
    if not _DEPS_OK:
        pytest.skip("integration deps missing")
    with PostgresContainer("postgres:16-alpine") as pg:
        yield pg.get_connection_url().replace("postgresql+psycopg2", "postgresql")


@pytest.fixture(scope="session")
def _schema_conn(pg_dsn: str) -> Iterator[object]:
    conn = psycopg.connect(pg_dsn, autocommit=True)
    apply_schema(PsycopgAdapter(conn))  # 001_core + 002_example_todo
    yield conn
    conn.close()


@pytest.fixture()
def conn(_schema_conn: object, pg_dsn: str) -> Iterator[object]:
    """每个测试一条干净连接; 测试前清空账本与示例实体表."""
    c = psycopg.connect(pg_dsn, autocommit=True)
    with c.cursor() as cur:
        cur.execute(
            "TRUNCATE l15_change_intents, todo_item, project RESTART IDENTITY CASCADE"
        )
    yield c
    c.close()


@pytest.fixture()
def ledger(conn: object):
    """装配好的 MemoryLedger (经组合根 open_postgres 接线)."""
    return open_postgres(
        conn,
        auto_apply=AutoApplyPolicy.low_risk_for(["todo_item", "project"]),
    )


@pytest.fixture()
def make_todo(conn: object):
    """建一条 todo_item 并返回其 id."""

    def _make(user_id: str = "u1", title: str = "买菜", **cols: object) -> int:
        keys = ["user_id", "title", *cols.keys()]
        vals = [user_id, title, *cols.values()]
        placeholders = ", ".join(["%s"] * len(vals))
        with conn.cursor() as cur:  # type: ignore[attr-defined]
            cur.execute(
                f"INSERT INTO todo_item ({', '.join(keys)}) "
                f"VALUES ({placeholders}) RETURNING id",
                vals,
            )
            return int(cur.fetchone()[0])

    return _make
