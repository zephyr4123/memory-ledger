"""集成: 默认 schema (001+002) 行为稳定性守护.

Step 1 把 001 的匿名 CHECK 命名为 chk_target_entity (behavior-equivalent rename).
本测试钉死: 命名约束存在、白名单只收 todo_item/project、未知实体仍被 CheckViolation
拒绝 —— 证明 58 项基线 schema 没有因命名而回归, 且 anti-LLM-noise 闸门仍在默认 path 生效.
"""

from __future__ import annotations

import psycopg
import pytest


def test_target_entity_check_is_named(conn):
    with conn.cursor() as cur:
        cur.execute(
            """
            SELECT 1 FROM pg_constraint
            WHERE conname = 'chk_target_entity'
              AND conrelid = 'l15_change_intents'::regclass
            """
        )
        assert cur.fetchone() is not None, "命名约束 chk_target_entity 应存在"


@pytest.mark.parametrize("entity", ["todo_item", "project"])
def test_whitelisted_entities_accepted(conn, entity):
    # 直接裸插一条该实体的合法 ASSERT, 应通过 (证明白名单仍收这两个)
    with conn.cursor() as cur:
        cur.execute(
            """
            INSERT INTO l15_change_intents
              (user_id,kind,target_entity,target_row_id,patch_json,
               source_layer,source_table,source_id,status,applied_at)
            VALUES ('u1','ASSERT',%s,'1','{"a":1}'::jsonb,
                    'L2_CHAT','t',%s,'APPLIED',now())
            """,
            [entity, f"sid_{entity}"],
        )  # 不抛即通过


@pytest.mark.parametrize("entity", ["person", "tasks", "todos", "TodoItem"])
def test_unknown_entity_rejected_by_named_check(conn, entity):
    # 未注册实体 (含 LLM 易写错的别名) 在默认 path 被命名 CHECK 拒绝
    with conn.cursor() as cur, pytest.raises(psycopg.errors.CheckViolation):
        cur.execute(
            """
            INSERT INTO l15_change_intents
              (user_id,kind,target_entity,target_row_id,patch_json,
               source_layer,source_table,source_id,status,applied_at)
            VALUES ('u1','ASSERT',%s,'1','{"a":1}'::jsonb,
                    'L2_CHAT','t','sid','APPLIED',now())
            """,
            [entity],
        )
