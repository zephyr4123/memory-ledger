"""集成: 实体注册表 (003) — FK 替 CHECK 守住 anti-LLM-noise + 注册即有函数."""

from __future__ import annotations

import psycopg
import pytest


def test_fk_rejects_unregistered_entity(crm_conn):
    # 注册表 path: 未注册实体写入被 ForeignKeyViolation 拒 (等价原 CheckViolation)
    with crm_conn.cursor() as cur, pytest.raises(psycopg.errors.ForeignKeyViolation):
        cur.execute(
            """
            INSERT INTO l15_change_intents
              (user_id,kind,target_entity,target_row_id,patch_json,
               source_layer,source_table,source_id,status,applied_at)
            VALUES ('u1','ASSERT','tasks','1','{"a":1}'::jsonb,
                    'L2_CHAT','t','sid','APPLIED',now())
            """
        )


def test_registered_entities_present(crm_conn):
    with crm_conn.cursor() as cur:
        cur.execute("SELECT name FROM l15_entity ORDER BY name")
        names = [r[0] for r in cur.fetchall()]
    assert names == ["person", "project", "todo_item"]


def test_every_registered_entity_has_live_effective_fn(crm_conn):
    """关闭注册表唯一的新失效模式: 注册了但没函数. 每行的 effective_fn 必须可解析."""
    with crm_conn.cursor() as cur:
        cur.execute("SELECT name, effective_fn FROM l15_entity")
        rows = cur.fetchall()
        assert rows, "应至少注册了 todo_item/project/person"
        for name, fn in rows:
            cur.execute(
                "SELECT to_regprocedure(%s)", [f"{fn}(text,bigint,timestamptz)"]
            )
            oid = cur.fetchone()[0]
            assert oid is not None, f"实体 {name!r} 注册了 {fn!r} 但函数不存在"


def test_registering_new_entity_is_an_insert_not_ddl(crm_conn):
    # "加实体" 在注册表 path 下是 INSERT —— 注册后该实体的 intent 即可写入
    with crm_conn.cursor() as cur:
        cur.execute(
            "INSERT INTO l15_entity (name, effective_fn) VALUES "
            "('company', 'effective_company_at')"
        )
        # 注册后, FK 放行 company 的 intent (无需 ALTER l15_change_intents)
        cur.execute(
            """
            INSERT INTO l15_change_intents
              (user_id,kind,target_entity,target_row_id,patch_json,
               source_layer,source_table,source_id,status,applied_at)
            VALUES ('u1','ASSERT','company','1','{"a":1}'::jsonb,
                    'L2_CHAT','t','sid','APPLIED',now())
            RETURNING id
            """
        )
        assert cur.fetchone()[0] is not None
