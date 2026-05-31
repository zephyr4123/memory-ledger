"""集成: 幂等 (High bug — 同 source 重复写应去重, 防 retry/双提交)."""

from __future__ import annotations

import psycopg
import pytest


def test_duplicate_source_returns_same_id(ledger, make_todo):
    tid = make_todo()
    kw = dict(
        user_id="u1", kind="ASSERT", target_entity="todo_item",
        target_row_id=str(tid), patch_json={"recipient": "mom"},
        source_layer="L2_CHAT", source_table="chat_message", source_id="msg42",
        confidence=0.9,
    )
    first = ledger.insert_intent(**kw)
    second = ledger.insert_intent(**kw)  # 完全相同的 source → 幂等
    assert first is not None and first == second


def test_idempotent_assert_not_duplicated_in_snapshot(ledger, make_todo):
    tid = make_todo()
    for _ in range(3):
        ledger.insert_intent(
            user_id="u1", kind="ASSERT", target_entity="todo_item",
            target_row_id=str(tid), patch_json={"recipient": "mom"},
            source_layer="L2_CHAT", source_table="chat_message", source_id="dup",
            confidence=0.9,
        )
    eff = ledger.effective("todo_item", "u1", tid)
    assert len(eff["assertions"]) == 1  # 不堆叠


def test_unique_index_backstops_raw_duplicate(conn):
    def ins():
        with conn.cursor() as cur:
            cur.execute(
                """
                INSERT INTO l15_change_intents
                  (user_id,kind,target_entity,target_row_id,patch_json,
                   source_layer,source_table,source_id,status,applied_at)
                VALUES ('u1','ASSERT','todo_item','1','{"a":1}'::jsonb,
                        'L2_CHAT','chat_message','raw1','APPLIED',now())
                """
            )

    ins()
    with pytest.raises(psycopg.errors.UniqueViolation):
        ins()
