"""Personal-CRM demo 的组合根 —— 把所有件接好并跑完脚本 (6 个 ScriptedTurn).

可两种方式驱动:
  * run_demo(ledger, person_id): 用一个已装配好的 MemoryLedger (测试注入)
  * main(): 自起一个真 Postgres (需 DSN env), apply CRM 迁移链, 打印对话

确定性: 不读 Python 时钟/随机; 时间戳全由 DB clock_timestamp() 盖; 时光机锚点
从 DB 的 intent 行取 (见 test_crm_demo). banner 的"采纳/拒绝"由脚本的
confirm_after / reject_field 提示编排 (模拟用户拍板)。
"""

from __future__ import annotations

import os
import sys
from dataclasses import dataclass
from typing import Any

from memory_ledger import MemoryLedger
from memory_ledger.application.agent_loop import AgentLoop, Banner

from .policy import FIELD_ALIASES, VALUE_ALIASES
from .responder import MockResponder
from .snapshot import build_person_snapshot
from .transcript import SEED_PERSON, TRANSCRIPT, ScriptedTurn


@dataclass
class DemoLog:
    """一轮对话的可读记录 (供 demo 打印 / 测试断言)."""

    turn: int
    utterance: str
    reply: str
    banners: tuple[Banner, ...]
    action: str  # 'confirm' / 'reject:<field>' / '-'


def run_transcript(
    ledger: MemoryLedger,
    person_id: int,
    *,
    user_id: str = "u1",
    script: tuple[ScriptedTurn, ...] = TRANSCRIPT,
) -> list[DemoLog]:
    """跑完整脚本, 返回每轮日志. ledger 须已 apply CRM 迁移 + person seed 行已建.

    banner 处理: 收集本轮 PROPOSED PATCH; 若该轮 confirm_after, 确认它们;
    若某轮 reject_field, 拒绝之前仍 pending 的该字段 PATCH。
    """
    loop = AgentLoop(
        ledger,
        MockResponder(script),
        lambda uid: build_person_snapshot(ledger, uid, [person_id]),
    )
    pending: dict[str, int] = {}  # field -> 待确认的 PATCH intent id
    logs: list[DemoLog] = []

    for turn, st in enumerate(script):
        result = loop.run_turn(
            user_id, st.utterance, turn, source_id=st.source_id, snapshot_scope=turn
        )
        for b in result.banners:
            if b.target_field:
                pending[b.target_field] = b.intent_id

        action = "-"
        if st.confirm_after and result.banners:
            ledger.confirm(user_id, [b.intent_id for b in result.banners])
            for b in result.banners:
                pending.pop(b.target_field, None)  # type: ignore[arg-type]
            action = "confirm"
        if st.reject_field and st.reject_field in pending:
            ledger.reject(user_id, [pending.pop(st.reject_field)], reason="user denied")
            action = f"reject:{st.reject_field}"

        logs.append(DemoLog(turn, st.utterance, result.reply, result.banners, action))

    return logs


def _seed_person(conn: Any, user_id: str = "u1") -> int:
    cols = ["user_id", *SEED_PERSON.keys()]
    vals = [user_id, *SEED_PERSON.values()]
    placeholders = ", ".join(["%s"] * len(vals))
    with conn.cursor() as cur:
        cur.execute(
            f"INSERT INTO person ({', '.join(cols)}) VALUES ({placeholders}) RETURNING id",
            vals,
        )
        return int(cur.fetchone()[0])


def main() -> int:  # pragma: no cover - 手动跑的入口
    dsn = os.environ.get("DATABASE_URL")
    if not dsn:
        print("set DATABASE_URL to a Postgres DSN to run the live demo", file=sys.stderr)
        return 2
    import psycopg

    from memory_ledger import PsycopgAdapter, open_postgres
    from memory_ledger.infrastructure.persistence.schema import CRM_MIGRATIONS, bundled_sql

    from .policy import crm_auto_apply_policy

    with psycopg.connect(dsn, autocommit=True) as conn:
        adapter = PsycopgAdapter(conn)
        # 幂等: 只在 person 表不存在时 apply 迁移链. 003 的 DROP CONSTRAINT/ADD FK 不可逆,
        # 重复 apply 会半途失败留下不一致 —— 先探测, 已迁移则跳过.
        already = adapter.fetchone("SELECT to_regclass('person') AS t")
        if already is None or already["t"] is None:
            for name in CRM_MIGRATIONS:
                adapter.execute(bundled_sql(name))
        pid = _seed_person(conn)
        ledger = open_postgres(
            conn,
            auto_apply=crm_auto_apply_policy(),
            field_aliases=FIELD_ALIASES,
            value_aliases=VALUE_ALIASES,
        )
        for log in run_transcript(ledger, pid):
            print(f"\n[turn {log.turn}] 用户: {log.utterance}")
            print(f"          助手: {log.reply}")
            for b in log.banners:
                print(f"          ⟳ 待确认: {b.target_field} → {b.proposed_value!r} "
                      f"(confidence {b.confidence})")
            if log.action != "-":
                print(f"          ✓ 动作: {log.action}")
    return 0


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
