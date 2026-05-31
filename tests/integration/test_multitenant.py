"""集成: 多租户隔离 (Critical bug — effective 函数曾不收 user_id 可跨租户读)."""

from __future__ import annotations

import pytest


def test_effective_requires_matching_user(ledger, make_todo):
    tid = make_todo(user_id="u1", title="u1 的私密待办", due_date="2026-06-01")
    # 攻击者 u2 拿到了 id, 试图用自己的 user_id 读 → 必须读不到
    assert ledger.effective("todo_item", "u2", tid) is None
    # 正主能读到
    owned = ledger.effective("todo_item", "u1", tid)
    assert owned is not None and owned["title"] == "u1 的私密待办"


def test_other_users_intents_never_merge(ledger, make_todo):
    tid = make_todo(user_id="u1", due_date="2026-06-01")
    # 即便有一条 user_id=u2 但 target_row_id 指向 u1 这条 todo 的 PATCH,
    # effective(u1) 也只合并 user_id=u1 的 intent.
    ledger.insert_intent(
        user_id="u2", kind="PATCH", target_entity="todo_item",
        target_row_id=str(tid), target_field="due_date",
        patch_json={"due_date": "1999-01-01"},
        source_layer="USER_DIRECT", source_table="chat_message", source_id="evil",
        confidence=1.0,
    )
    assert ledger.effective("todo_item", "u2", tid) is None
    eff = ledger.effective("todo_item", "u1", tid)
    assert str(eff["due_date_eff"]) == "2026-06-01"


@pytest.mark.parametrize("entity", ["todo_item", "project"])
def test_both_effective_functions_take_user_id(conn, entity):
    with conn.cursor() as cur:
        cur.execute(
            "SELECT pg_get_function_arguments(oid) FROM pg_proc WHERE proname = %s",
            [f"effective_{entity}_at"],
        )
        args = cur.fetchone()[0]
    assert args.startswith("p_user_id text")
