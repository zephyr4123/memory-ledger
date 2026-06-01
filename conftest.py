"""仓库根 pytest 配置 —— 共享 fixtures + 集成测试自动跳过 (tests/ 与 examples/ 共用).

放在仓库根, 让 tests/ 和 examples/ 两棵测试树都继承同一套 fixtures (单一来源).

测试分层:
  * 纯单元 (无 I/O): tests/unit/**, examples/**/tests/test_crm_snapshot|extractor.py
  * 集成 (需 docker 起 Postgres): tests/integration/**, examples/**/tests/test_crm_demo.py

跳过策略: 不靠路径启发, 而是看测试**是否请求了 DB fixture**(transitive fixturenames
含 pg_dsn). 任何用到真库的测试在 docker/testcontainers 依赖缺失时自动 skip ——
对 tests/ 与 examples/ 一视同仁, 新增集成测试无需手动打 marker.

fixtures 分两套, 共用同一个 session 级容器 (pg_dsn):
  * 默认 path (public schema, 001+002): conn / ledger / make_todo
  * CRM path (独立 crm schema, 001+002+003+004): crm_conn / crm_ledger / make_person
CRM 链含 003 的 ALTER l15_change_intents (CHECK→FK), 故隔离在独立 schema, 绝不污染默认 path.
"""

from __future__ import annotations

from collections.abc import Iterator

import pytest

try:
    import psycopg
    from testcontainers.postgres import PostgresContainer

    from memory_ledger import AutoApplyPolicy, PsycopgAdapter, apply_schema, open_postgres
    from memory_ledger.infrastructure.persistence.schema import CRM_MIGRATIONS, bundled_sql

    _DEPS_OK = True
    _IMPORT_ERR: Exception | None = None
except Exception as exc:
    _DEPS_OK = False
    _IMPORT_ERR = exc

_CRM_SCHEMA = "crm"


def pytest_collection_modifyitems(items: list[pytest.Item]) -> None:
    """依赖缺失时, 跳过任何 (transitive) 请求了 pg_dsn 的测试 —— 即所有 DB 集成测试."""
    if _DEPS_OK:
        return
    skip = pytest.mark.skip(reason=f"integration deps missing: {_IMPORT_ERR}")
    for item in items:
        if "pg_dsn" in getattr(item, "fixturenames", ()):
            item.add_marker(skip)


# ── 共用 session 级容器 ───────────────────────────────────────────────
@pytest.fixture(scope="session")
def pg_dsn() -> Iterator[str]:
    if not _DEPS_OK:
        pytest.skip("integration deps missing")
    with PostgresContainer("postgres:16-alpine") as pg:
        yield pg.get_connection_url().replace("postgresql+psycopg2", "postgresql")


# ── 默认 path (public schema, 001+002) ───────────────────────────────
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


# ── CRM path (独立 crm schema, 001+002+003+004) ──────────────────────
def _connect_crm(dsn: str):
    conn = psycopg.connect(dsn, autocommit=True)
    with conn.cursor() as cur:
        cur.execute(f"SET search_path = {_CRM_SCHEMA}")
    return conn


@pytest.fixture(scope="session")
def _crm_schema_conn(pg_dsn: str) -> Iterator[object]:
    """在独立 schema crm 上应用整条 CRM 迁移链 (隔离 003 的 ALTER, 不碰默认 path)."""
    admin = psycopg.connect(pg_dsn, autocommit=True)
    with admin.cursor() as cur:
        cur.execute(f"DROP SCHEMA IF EXISTS {_CRM_SCHEMA} CASCADE")
        cur.execute(f"CREATE SCHEMA {_CRM_SCHEMA}")
    admin.close()

    conn = _connect_crm(pg_dsn)
    adapter = PsycopgAdapter(conn)
    for name in CRM_MIGRATIONS:
        adapter.execute(bundled_sql(name))
    yield conn
    conn.close()


@pytest.fixture()
def crm_conn(_crm_schema_conn: object, pg_dsn: str) -> Iterator[object]:
    """每个测试一条 search_path=crm 的干净连接; 先清空账本 + 业务表 + 把注册表复位到
    canonical 三行 (todo_item/project/person), 防止某测试注册的额外实体跨测试残留."""
    c = _connect_crm(pg_dsn)
    with c.cursor() as cur:
        # 注: l15_change_intents 对 l15_entity 有 FK, 先清账本再删多余注册行
        cur.execute(
            "TRUNCATE l15_change_intents, todo_item, project, person "
            "RESTART IDENTITY CASCADE"
        )
        cur.execute(
            "DELETE FROM l15_entity "
            "WHERE name NOT IN ('todo_item', 'project', 'person')"
        )
    yield c
    c.close()


@pytest.fixture()
def crm_ledger(crm_conn: object):
    """装配好的 CRM MemoryLedger, person 低危 kind auto-apply, PATCH 走 banner."""
    return open_postgres(crm_conn, auto_apply=AutoApplyPolicy.low_risk_for(["person"]))


@pytest.fixture()
def make_person(crm_conn: object):
    """建一条 person 并返回 id."""

    def _make(user_id: str = "u1", full_name: str = "Sarah Lin", **cols: object) -> int:
        keys = ["user_id", "full_name", *cols.keys()]
        vals = [user_id, full_name, *cols.values()]
        placeholders = ", ".join(["%s"] * len(vals))
        with crm_conn.cursor() as cur:  # type: ignore[attr-defined]
            cur.execute(
                f"INSERT INTO person ({', '.join(keys)}) "
                f"VALUES ({placeholders}) RETURNING id",
                vals,
            )
            return int(cur.fetchone()[0])

    return _make
