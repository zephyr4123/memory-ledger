"""集成: auto-supersede 触发器 + 一字段一条 live PATCH 不变量."""

from __future__ import annotations


def _apply_patch(ledger, user, tid, field, value, sid):
    iid = ledger.insert_intent(
        user_id=user, kind="PATCH", target_entity="todo_item",
        target_row_id=str(tid), target_field=field, patch_json={field: value},
        source_layer="L2_CHAT", source_table="chat_message", source_id=sid,
        confidence=0.95,
    )
    ledger.confirm(user, [iid])
    return iid


def test_new_patch_auto_supersedes_old(ledger, make_todo, conn):
    tid = make_todo(due_date="2026-06-01")
    i1 = _apply_patch(ledger, "u1", tid, "due_date", "2026-05-30", "m1")
    i2 = _apply_patch(ledger, "u1", tid, "due_date", "2026-05-28", "m2")

    with conn.cursor() as cur:
        cur.execute("SELECT id, status, superseded_by FROM l15_change_intents ORDER BY id")
        rows = {r[0]: (r[1], r[2]) for r in cur.fetchall()}
    assert rows[i1] == ("SUPERSEDED", i2)
    assert rows[i2][0] == "APPLIED"


def test_at_most_one_live_patch_per_field(ledger, make_todo, conn):
    tid = make_todo(due_date="2026-06-01")
    for n, d in enumerate(["2026-05-30", "2026-05-29", "2026-05-28"]):
        _apply_patch(ledger, "u1", tid, "due_date", d, f"m{n}")
    with conn.cursor() as cur:
        cur.execute(
            """
            SELECT COUNT(*) FROM l15_change_intents
            WHERE kind='PATCH' AND status='APPLIED' AND superseded_by IS NULL
              AND target_field='due_date'
            """
        )
        assert cur.fetchone()[0] == 1


def test_different_fields_dont_supersede_each_other(ledger, make_todo):
    tid = make_todo(due_date="2026-06-01", priority=3)
    _apply_patch(ledger, "u1", tid, "due_date", "2026-05-30", "m1")
    _apply_patch(ledger, "u1", tid, "priority", 5, "m2")
    eff = ledger.effective("todo_item", "u1", tid)
    assert str(eff["due_date_eff"]) == "2026-05-30"
    assert eff["priority_eff"] == 5  # 两个字段各自 live
