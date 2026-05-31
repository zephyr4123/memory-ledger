"""集成: status ↔ 时间戳列耦合 CHECK (Critical bug — 状态翻转漏写时间戳会静默生效)."""

from __future__ import annotations

import psycopg
import pytest


def _raw_insert_applied_patch(conn, **over):
    cols = {
        "user_id": "u1", "kind": "PATCH", "target_entity": "todo_item",
        "target_row_id": "1", "target_field": "due_date",
        "patch_json": '{"due_date":"2026-05-30"}', "source_layer": "L2_CHAT",
        "source_table": "chat_message", "source_id": "m1",
        "status": "APPLIED", "applied_at": "now()",
    }
    cols.update(over)
    with conn.cursor() as cur:
        cur.execute(
            """
            INSERT INTO l15_change_intents
              (user_id,kind,target_entity,target_row_id,target_field,patch_json,
               source_layer,source_table,source_id,status,applied_at)
            VALUES (%(user_id)s,%(kind)s,%(target_entity)s,%(target_row_id)s,
                    %(target_field)s,%(patch_json)s::jsonb,%(source_layer)s,
                    %(source_table)s,%(source_id)s,%(status)s,
                    CASE WHEN %(applied_at)s='now()' THEN now() ELSE NULL END)
            RETURNING id
            """,
            cols,
        )
        return int(cur.fetchone()[0])


def test_rejected_without_timestamp_is_refused(conn):
    iid = _raw_insert_applied_patch(conn, source_id="r1")
    with conn.cursor() as cur, pytest.raises(psycopg.errors.CheckViolation):
        cur.execute("UPDATE l15_change_intents SET status='REJECTED' WHERE id=%s", [iid])


def test_superseded_without_ref_is_refused(conn):
    iid = _raw_insert_applied_patch(conn, source_id="s1")
    with conn.cursor() as cur, pytest.raises(psycopg.errors.CheckViolation):
        cur.execute("UPDATE l15_change_intents SET status='SUPERSEDED' WHERE id=%s", [iid])


def test_applied_without_timestamp_is_refused(conn):
    with conn.cursor() as cur, pytest.raises(psycopg.errors.CheckViolation):
        cur.execute(
            """
            INSERT INTO l15_change_intents
              (user_id,kind,target_entity,target_row_id,target_field,patch_json,
               source_layer,source_table,source_id,status)
            VALUES ('u1','PATCH','todo_item','1','due_date',
                    '{"due_date":"x"}'::jsonb,'L2_CHAT','t','m','APPLIED')
            """
        )


def test_unknown_kind_rejected(conn):
    with conn.cursor() as cur, pytest.raises(psycopg.errors.CheckViolation):
        cur.execute(
            """
            INSERT INTO l15_change_intents
              (user_id,kind,target_entity,patch_json,source_layer,source_table,source_id)
            VALUES ('u1','WEIRD','todo_item','{"a":1}'::jsonb,'L2_CHAT','t','m')
            """
        )
