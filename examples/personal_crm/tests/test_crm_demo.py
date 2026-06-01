"""集成 (示例, testcontainers): 端到端跑完脚本 (6 个 ScriptedTurn), 断言三大差异化真实发生.

复用仓库根 conftest.py 的 crm_conn fixture (独立 crm schema, 已 apply
001+002+003+004). 本测试是整个 Phase B 的"皇冠证明":
  1. SUPERSEDE 链   —— Acme PATCH 被 Globex superseded, 恰一条 live, employer_eff='Globex'
  2. DB 锚点时光机  —— 从 DB 取 Acme PATCH 的 applied_at 作 as_of, 回看得 'Acme' (零 Python 时钟)
  3. 逐字溯源       —— assertions[] 里的 source_quote 等于脚本原话子串
  4. BANNER/拒绝弧  —— Berlin location PATCH 先 PROPOSED 挂起, 后 REJECTED, location_eff 仍 'SF'
"""

from __future__ import annotations

from examples.personal_crm.policy import FIELD_ALIASES, VALUE_ALIASES
from examples.personal_crm.run_demo import _seed_person, run_transcript
from examples.personal_crm.transcript import SEED_PERSON


def _ledger_with_aliases(crm_conn):
    # crm_ledger fixture 不带别名; demo 要别名, 这里用同连接重新装配一个带别名的 ledger
    from examples.personal_crm.policy import crm_auto_apply_policy
    from memory_ledger import open_postgres

    return open_postgres(
        crm_conn,
        auto_apply=crm_auto_apply_policy(),
        field_aliases=FIELD_ALIASES,
        value_aliases=VALUE_ALIASES,
    )


def test_full_crm_demo_three_differentiators(crm_conn):
    ledger = _ledger_with_aliases(crm_conn)
    pid = _seed_person(crm_conn, user_id="u1")
    assert pid == 1  # transcript 用 target_row_id='1'

    logs = run_transcript(ledger, pid, user_id="u1")
    assert len(logs) == 6  # 6 个脚本轮 (含 confirm/reject 编排在轮内)

    # ── 差异化 1: SUPERSEDE 链 + effective 真相 ──────────────────────
    eff = ledger.effective("person", "u1", pid)
    assert eff["employer_eff"] == "Globex"  # 最终真相
    assert eff["employer_raw"] == "Acme Corp"  # 原始 seed 不变

    with crm_conn.cursor() as cur:
        cur.execute(
            "SELECT COUNT(*) FROM l15_change_intents WHERE target_entity='person' "
            "AND target_field='employer' AND kind='PATCH' AND status='APPLIED' "
            "AND superseded_by IS NULL"
        )
        assert cur.fetchone()[0] == 1  # 恰一条 live employer PATCH

        # Acme PATCH 被 SUPERSEDED, 指向 Globex
        cur.execute(
            "SELECT status, superseded_by FROM l15_change_intents "
            "WHERE target_field='employer' AND patch_json->>'employer'='Acme'"
        )
        acme_status, acme_superseded_by = cur.fetchone()
        assert acme_status == "SUPERSEDED"
        cur.execute(
            "SELECT patch_json->>'employer' FROM l15_change_intents WHERE id=%s",
            [acme_superseded_by],
        )
        assert cur.fetchone()[0] == "Globex"  # supersede 链指向正确

        # ── 差异化 2: DB 锚点时光机 (零 Python 时钟) ──────────────────
        cur.execute(
            "SELECT applied_at FROM l15_change_intents "
            "WHERE target_field='employer' AND patch_json->>'employer'='Acme'"
        )
        acme_applied_at = cur.fetchone()[0]  # 从 DB 取锚点, 不读 Python 时钟

    past = ledger.effective("person", "u1", pid, as_of=acme_applied_at)
    assert past["employer_eff"] == "Acme"  # 那个时点真相是 Acme (Globex 还没生效)

    # ── 差异化 3: 逐字溯源 ──────────────────────────────────────────
    quotes = [a["source_quote"] for a in eff["assertions"]]
    assert "she moved to Globex" in quotes  # 原话在结构化数据里
    assert "she just started at Acme" in quotes

    # ── 差异化 4: BANNER → 拒绝弧 ───────────────────────────────────
    assert eff["location_eff"] == "San Francisco"  # Berlin 被拒, 仍 SF
    with crm_conn.cursor() as cur:
        cur.execute(
            "SELECT status, rejected_at FROM l15_change_intents "
            "WHERE target_field='location' AND patch_json->>'location'='Berlin'"
        )
        loc_status, loc_rejected_at = cur.fetchone()
        assert loc_status == "REJECTED"
        assert loc_rejected_at is not None  # 拒绝时间戳已写 (状态↔时间戳耦合)


def test_demo_is_deterministic_across_runs(crm_conn):
    """同脚本两次完整跑 (各自清库), reply 序列与最终 employer 必须一致."""
    def once() -> tuple[list[str], str]:
        with crm_conn.cursor() as cur:
            cur.execute(
                "TRUNCATE l15_change_intents, person RESTART IDENTITY CASCADE"
            )
        ledger = _ledger_with_aliases(crm_conn)
        pid = _seed_person(crm_conn, user_id="u1")
        logs = run_transcript(ledger, pid, user_id="u1")
        eff = ledger.effective("person", "u1", pid)
        return [lg.reply for lg in logs], eff["employer_eff"]

    r1 = once()
    r2 = once()
    assert r1 == r2
    assert r1[1] == "Globex"


def test_seed_person_matches_transcript_assumptions(crm_conn):
    # 守护: seed 字段与脚本假设一致 (employer_raw 必须是 'Acme Corp')
    assert SEED_PERSON["employer"] == "Acme Corp"
    assert SEED_PERSON["location"] == "San Francisco"
