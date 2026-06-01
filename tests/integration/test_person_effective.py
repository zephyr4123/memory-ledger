"""集成: person 实体镜像 todo 的全部不变量 (证明新实体复用核心机制无回归)."""

from __future__ import annotations

import psycopg
import pytest


def _patch(ledger, user, pid, field, value, **kw):
    return ledger.insert_intent(
        user_id=user, kind="PATCH", target_entity="person",
        target_row_id=str(pid), target_field=field, patch_json={field: value},
        source_layer=kw.pop("source_layer", "L2_CHAT"),
        source_table="chat_message", source_id=kw.pop("source_id", "m1"),
        confidence=kw.pop("confidence", 0.95), **kw,
    )


def test_person_no_intents_returns_raw(crm_ledger, make_person):
    pid = make_person(employer="Acme Corp")
    eff = crm_ledger.effective("person", "u1", pid)
    assert eff is not None
    assert eff["employer_eff"] == "Acme Corp"
    assert eff["assertions"] == [] and eff["flags"] == []


def test_person_patch_eff_after_confirm(crm_ledger, make_person):
    pid = make_person(employer="Acme Corp")
    iid = _patch(crm_ledger, "u1", pid, "employer", "Acme")
    assert crm_ledger.effective("person", "u1", pid)["employer_eff"] == "Acme Corp"  # PROPOSED
    crm_ledger.confirm("u1", [iid])
    assert crm_ledger.effective("person", "u1", pid)["employer_eff"] == "Acme"


def test_person_winner_priority_beats_confidence(crm_ledger, make_person, crm_conn):
    """跨 source_layer 共存时, effective 按 source_priority 仲裁 (设计 §5):
    USER_DIRECT(高权威,低置信) 压 AGENT_INFERENCE(低权威,高置信).

    关键: 这两条 PATCH 因 source_layer 不同, **都 live** (不互相 supersede),
    所以 patch_latest 的 priority/confidence ORDER BY 真正被触发 —— 旧版本里
    confirm 会让其中一条 supersede 另一条, 令该断言形同虚设 (vacuous)."""
    pid = make_person(comm_pref="email")
    # AGENT 先写、高置信; USER 后写、低置信 —— 若是 last-writer 或 confidence-wins, agent 应赢
    a = _patch(crm_ledger, "u1", pid, "comm_pref", "sms", source_layer="AGENT_INFERENCE",
               confidence=0.95, source_id="agent")
    b = _patch(crm_ledger, "u1", pid, "comm_pref", "phone", source_layer="USER_DIRECT",
               confidence=0.70, source_id="user")
    crm_ledger.confirm("u1", [a, b])
    # 两条都应仍 live (跨 layer 不互相 supersede)
    with crm_conn.cursor() as cur:
        cur.execute(
            "SELECT COUNT(*) FROM l15_change_intents WHERE kind='PATCH' "
            "AND status='APPLIED' AND superseded_by IS NULL "
            "AND target_entity='person' AND target_field='comm_pref'"
        )
        assert cur.fetchone()[0] == 2, "跨 layer 的 PATCH 应共存, 不互相 supersede"
    # priority 仲裁: USER_DIRECT 赢, 尽管它后写且置信更低
    assert crm_ledger.effective("person", "u1", pid)["comm_pref_eff"] == "phone"


def test_person_same_layer_supersede_one_live(crm_ledger, make_person, crm_conn):
    """同一 source_layer 内连续改 (改口) → 后写 supersede 前写, 恰一条 live."""
    pid = make_person(employer="Acme Corp")
    for n, e in enumerate(["Acme", "Globex", "Initech"]):
        iid = _patch(crm_ledger, "u1", pid, "employer", e,
                     source_layer="L2_CHAT", source_id=f"m{n}")
        crm_ledger.confirm("u1", [iid])
    with crm_conn.cursor() as cur:
        cur.execute(
            "SELECT COUNT(*) FROM l15_change_intents WHERE kind='PATCH' "
            "AND status='APPLIED' AND superseded_by IS NULL "
            "AND target_entity='person' AND target_field='employer' "
            "AND source_layer='L2_CHAT'"
        )
        assert cur.fetchone()[0] == 1  # 同 layer 改口: 恰一条 live
    assert crm_ledger.effective("person", "u1", pid)["employer_eff"] == "Initech"


def test_person_idempotency(crm_ledger, make_person):
    pid = make_person()
    kw = dict(
        user_id="u1", kind="ASSERT", target_entity="person", target_row_id=str(pid),
        patch_json={"note": "met at PyCon"}, source_layer="L2_CHAT",
        source_table="chat_message", source_id="dup", confidence=0.9,
    )
    a = crm_ledger.insert_intent(**kw)
    b = crm_ledger.insert_intent(**kw)
    assert a == b
    assert len(crm_ledger.effective("person", "u1", pid)["assertions"]) == 1


def test_person_multitenant_isolation(crm_ledger, make_person):
    pid = make_person(user_id="u1", full_name="u1 的联系人")
    assert crm_ledger.effective("person", "u2", pid) is None  # 越权读不到
    assert crm_ledger.effective("person", "u1", pid)["full_name_eff"] == "u1 的联系人"


def test_person_time_travel(crm_ledger, make_person, crm_conn):
    # 同 layer 连续改口 (L2_CHAT): Acme → Globex (后者 supersede 前者)
    i1 = _patch(crm_ledger, "u1", pid := make_person(employer="Acme Corp"),
                "employer", "Acme", source_layer="L2_CHAT", source_id="m1")
    crm_ledger.confirm("u1", [i1])
    i2 = _patch(crm_ledger, "u1", pid, "employer", "Globex",
                source_layer="L2_CHAT", source_id="m2")
    crm_ledger.confirm("u1", [i2])

    # 时光机锚点从 DB 取 (零 Python 时钟, 避免客户端/DB 时钟偏移导致 flaky):
    # 取 i1 (Acme) 与 i2 (Globex) 的 applied_at, 用其严格中间点查 i1-only 窗口.
    with crm_conn.cursor() as cur:
        cur.execute(
            "SELECT id, applied_at FROM l15_change_intents "
            "WHERE id = ANY(%s) ORDER BY applied_at", [[i1, i2]]
        )
        rows = cur.fetchall()
        t1, t2 = rows[0][1], rows[1][1]
        # 中点 (DB 侧时间运算, 不读 Python 时钟)
        cur.execute("SELECT %s + (%s - %s) / 2 AS mid", [t1, t2, t1])
        mid = cur.fetchone()[0]
        cur.execute("SELECT %s - INTERVAL '365 days' AS past", [t1])
        before_any = cur.fetchone()[0]

    assert crm_ledger.effective("person", "u1", pid)["employer_eff"] == "Globex"
    assert crm_ledger.effective("person", "u1", pid, as_of=mid)["employer_eff"] == "Acme"
    way_past = crm_ledger.effective("person", "u1", pid, as_of=before_any)
    assert way_past["employer_eff"] == "Acme Corp"


def test_person_comm_pref_enum_check(crm_ledger, make_person, crm_conn):
    # comm_pref 的 CHECK 是业务表层 (raw 列), 直接非法 raw 写入应被拒
    with crm_conn.cursor() as cur, pytest.raises(psycopg.errors.CheckViolation):
        cur.execute("INSERT INTO person (user_id, full_name, comm_pref) "
                    "VALUES ('u1','X','telepathy')")
