"""集成: confirm / reject 生命周期 + auto-apply 路径."""

from __future__ import annotations


def test_assert_auto_applies_immediately(ledger, make_todo, conn):
    tid = make_todo()
    ledger.insert_intent(
        user_id="u1", kind="ASSERT", target_entity="todo_item",
        target_row_id=str(tid), patch_json={"recipient": "mom"},
        source_layer="L2_CHAT", source_table="chat_message", source_id="m1",
        confidence=0.9,
    )
    with conn.cursor() as cur:
        cur.execute("SELECT status FROM l15_change_intents")
        assert cur.fetchone()[0] == "APPLIED"
    eff = ledger.effective("todo_item", "u1", tid)
    assert eff["assertions"][0]["payload"]["recipient"] == "mom"


def test_patch_lands_proposed_then_confirm(ledger, make_todo, conn):
    tid = make_todo(due_date="2026-06-01")
    iid = ledger.insert_intent(
        user_id="u1", kind="PATCH", target_entity="todo_item",
        target_row_id=str(tid), target_field="due_date",
        patch_json={"due_date": "2026-05-30"},
        source_layer="AGENT_INFERENCE", source_table="chat_message", source_id="m1",
        confidence=0.9,
    )
    with conn.cursor() as cur:
        cur.execute("SELECT status, applied_at FROM l15_change_intents WHERE id=%s", [iid])
        status, applied_at = cur.fetchone()
    assert status == "PROPOSED" and applied_at is None
    assert str(ledger.effective("todo_item", "u1", tid)["due_date_eff"]) == "2026-06-01"
    ledger.confirm("u1", [iid])
    assert str(ledger.effective("todo_item", "u1", tid)["due_date_eff"]) == "2026-05-30"


def test_reject_keeps_effective_unchanged(ledger, make_todo):
    tid = make_todo(due_date="2026-06-01")
    iid = ledger.insert_intent(
        user_id="u1", kind="PATCH", target_entity="todo_item",
        target_row_id=str(tid), target_field="due_date",
        patch_json={"due_date": "2026-05-30"},
        source_layer="AGENT_INFERENCE", source_table="chat_message", source_id="m1",
        confidence=0.9,
    )
    assert ledger.reject("u1", [iid], "用户说不用改") == 1
    assert str(ledger.effective("todo_item", "u1", tid)["due_date_eff"]) == "2026-06-01"


def test_confirm_wrong_user_is_noop(ledger, make_todo):
    tid = make_todo(due_date="2026-06-01")
    iid = ledger.insert_intent(
        user_id="u1", kind="PATCH", target_entity="todo_item",
        target_row_id=str(tid), target_field="due_date",
        patch_json={"due_date": "2026-05-30"},
        source_layer="AGENT_INFERENCE", source_table="chat_message", source_id="m1",
        confidence=0.9,
    )
    assert ledger.confirm("u2", [iid]) == 0  # 不是 u2 的, 确认不了
