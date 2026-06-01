"""集成: list_intents/history 原始账本流水读 (审计时间轴 + 逐字溯源用).

与 effective (合成真相) 互补 —— 这里验证返回的是构成真相的每条原始 intent 行,
按时间升序, 多租户隔离, 且能按 status 过滤。
"""

from __future__ import annotations


def test_history_returns_raw_intents_in_chronological_order(ledger, make_todo):
    tid = make_todo(due_date="2026-06-01")
    a = ledger.insert_intent(
        user_id="u1", kind="ASSERT", target_entity="todo_item",
        target_row_id=str(tid), patch_json={"recipient": "mom"},
        source_layer="L2_CHAT", source_table="chat_message", source_id="m1",
        source_quote="给妈妈买菜", confidence=0.9,
    )
    p = ledger.insert_intent(
        user_id="u1", kind="PATCH", target_entity="todo_item",
        target_row_id=str(tid), target_field="due_date",
        patch_json={"due_date": "2026-05-30"},
        source_layer="AGENT_INFERENCE", source_table="chat_message", source_id="m2",
        source_quote="改成周五到期", confidence=0.8,
    )

    rows = ledger.history("todo_item", "u1", tid)
    assert [r["id"] for r in rows] == [a, p]  # 时间升序 (a 先于 p)
    # 不合成: 每条原始 intent 的 kind/status/溯源字段都在
    assert rows[0]["kind"] == "ASSERT" and rows[0]["status"] == "APPLIED"
    assert rows[1]["kind"] == "PATCH" and rows[1]["status"] == "PROPOSED"
    assert rows[0]["source_quote"] == "给妈妈买菜"  # 逐字溯源
    assert rows[1]["target_field"] == "due_date"
    assert rows[1]["source_layer"] == "AGENT_INFERENCE"


def test_history_reflects_status_transitions_and_filters(ledger, make_todo):
    tid = make_todo(due_date="2026-06-01")
    p = ledger.insert_intent(
        user_id="u1", kind="PATCH", target_entity="todo_item",
        target_row_id=str(tid), target_field="due_date",
        patch_json={"due_date": "2026-05-30"},
        source_layer="AGENT_INFERENCE", source_table="chat_message", source_id="m1",
        confidence=0.9,
    )
    ledger.confirm("u1", [p])  # PROPOSED → APPLIED

    applied = ledger.history("todo_item", "u1", tid, statuses=["APPLIED"])
    assert [r["id"] for r in applied] == [p]
    assert applied[0]["applied_at"] is not None
    # 过滤后该状态为空 (已不再是 PROPOSED)
    assert ledger.history("todo_item", "u1", tid, statuses=["PROPOSED"]) == []


def test_history_is_multitenant_isolated(ledger, make_todo):
    tid = make_todo(due_date="2026-06-01")
    ledger.insert_intent(
        user_id="u1", kind="ASSERT", target_entity="todo_item",
        target_row_id=str(tid), patch_json={"recipient": "mom"},
        source_layer="L2_CHAT", source_table="chat_message", source_id="m1",
        confidence=0.9,
    )
    assert ledger.history("todo_item", "u1", tid)  # u1 看得到
    assert ledger.history("todo_item", "u2", tid) == []  # 越权读不到
