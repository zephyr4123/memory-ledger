"""集成: effective view 基本语义 + PATCH winner 排序 + 时光机."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta


def _patch(ledger, user, todo_id, field, value, **kw):
    return ledger.insert_intent(
        user_id=user, kind="PATCH", target_entity="todo_item",
        target_row_id=str(todo_id), target_field=field,
        patch_json={field: value},
        source_layer=kw.pop("source_layer", "L2_CHAT"),
        source_table="chat_message", source_id=kw.pop("source_id", "msg1"),
        confidence=kw.pop("confidence", 0.95), **kw,
    )


def test_no_intents_returns_raw_row(ledger, make_todo):
    tid = make_todo(due_date="2026-06-01")
    eff = ledger.effective("todo_item", "u1", tid)
    assert eff is not None
    assert str(eff["due_date_eff"]) == "2026-06-01"
    assert eff["assertions"] == [] and eff["flags"] == []


def test_applied_patch_changes_eff_not_raw(ledger, make_todo):
    tid = make_todo(due_date="2026-06-01")
    iid = _patch(ledger, "u1", tid, "due_date", "2026-05-30")
    eff = ledger.effective("todo_item", "u1", tid)
    assert str(eff["due_date_eff"]) == "2026-06-01"  # 还没 confirm
    assert ledger.confirm("u1", [iid]) == 1
    eff = ledger.effective("todo_item", "u1", tid)
    assert str(eff["due_date_eff"]) == "2026-05-30"
    assert str(eff["due_date_raw"]) == "2026-06-01"


def test_patch_winner_priority_beats_confidence(ledger, make_todo):
    tid = make_todo(due_date="2026-06-01")
    a = _patch(ledger, "u1", tid, "priority", 5, source_layer="AGENT_INFERENCE",
               confidence=0.95, source_id="agent")
    b = _patch(ledger, "u1", tid, "priority", 1, source_layer="USER_DIRECT",
               confidence=0.70, source_id="user")
    ledger.confirm("u1", [a, b])
    eff = ledger.effective("todo_item", "u1", tid)
    assert eff["priority_eff"] == 1  # USER_DIRECT winner


def test_time_travel_sees_old_version(ledger, make_todo):
    tid = make_todo(due_date="2026-06-01")
    i1 = _patch(ledger, "u1", tid, "due_date", "2026-05-30", source_id="m1")
    ledger.confirm("u1", [i1])
    mid = datetime.now(UTC)
    i2 = _patch(ledger, "u1", tid, "due_date", "2026-05-28", source_id="m2")
    ledger.confirm("u1", [i2])

    now_eff = ledger.effective("todo_item", "u1", tid)
    assert str(now_eff["due_date_eff"]) == "2026-05-28"  # 最新

    past_eff = ledger.effective("todo_item", "u1", tid, as_of=mid)
    assert str(past_eff["due_date_eff"]) == "2026-05-30"  # 时光机回看旧版

    way_past = ledger.effective("todo_item", "u1", tid, as_of=mid - timedelta(days=365))
    assert str(way_past["due_date_eff"]) == "2026-06-01"  # 改动前 = raw
