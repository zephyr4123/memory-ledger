"""集成: EXPIRED 真落地 (High bug — 早期 EXPIRED 是 no-op, 标了也不影响 effective)."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta


def _apply(ledger, tid):
    iid = ledger.insert_intent(
        user_id="u1", kind="PATCH", target_entity="todo_item",
        target_row_id=str(tid), target_field="due_date",
        patch_json={"due_date": "2026-05-30"},
        source_layer="L2_CHAT", source_table="chat_message", source_id="m1",
        confidence=0.95,
    )
    ledger.confirm("u1", [iid])
    return iid


def test_expire_before_drops_from_effective(ledger, make_todo):
    tid = make_todo(due_date="2026-06-01")
    _apply(ledger, tid)
    assert str(ledger.effective("todo_item", "u1", tid)["due_date_eff"]) == "2026-05-30"

    n = ledger.expire_before(datetime.now(UTC) + timedelta(seconds=1))
    assert n == 1
    assert str(ledger.effective("todo_item", "u1", tid)["due_date_eff"]) == "2026-06-01"


def test_expired_still_visible_in_past_time_travel(ledger, make_todo):
    tid = make_todo(due_date="2026-06-01")
    _apply(ledger, tid)
    before_expire = datetime.now(UTC)
    ledger.expire_before(datetime.now(UTC) + timedelta(seconds=1))

    # 过期点之前的时光机查询仍应看到该 PATCH (expired_at 按 as_of 比较)
    past = ledger.effective("todo_item", "u1", tid, as_of=before_expire)
    assert str(past["due_date_eff"]) == "2026-05-30"
