"""启动时确定性预置 demo 数据 —— 让时光机/溯源/账本开箱即有料.

通过 ledger API(write_intent + confirm/reject)按真实生命周期构造 Sarah 的账本史:
  雇主 Acme Corp(raw) → Acme(确认) → Globex(确认, supersede Acme);
  location 一次低置信 Berlin 改动被**拒绝**(仍 SF)并留一条 FLAG; 另含注释/断言。
另置一个联系人 Marcus 填充列表。幂等: 已有该用户的 person 行则跳过。

注意: 这是 demo fixture, 不是产品逻辑。真实改动一律来自对话里的真 LLM。
"""

from __future__ import annotations

from typing import Any

from .db import ledger_for

_SARAH = {
    "full_name": "Sarah Lin",
    "employer": "Acme Corp",
    "role": "PM",
    "location": "San Francisco",
    "comm_pref": "email",
}
_MARCUS = {
    "full_name": "Marcus Reyes",
    "employer": "Initech",
    "role": "Designer",
    "location": "Austin",
    "comm_pref": "sms",
}


def _insert_person(conn: Any, user_id: str, cols: dict[str, str]) -> int:
    keys = ["user_id", *cols.keys()]
    vals = [user_id, *cols.values()]
    placeholders = ", ".join(["%s"] * len(vals))
    with conn.cursor() as cur:
        cur.execute(
            f"INSERT INTO person ({', '.join(keys)}) VALUES ({placeholders}) RETURNING id",
            vals,
        )
        return int(cur.fetchone()[0])


def already_seeded(conn: Any, user_id: str) -> bool:
    with conn.cursor() as cur:
        cur.execute("SELECT 1 FROM person WHERE user_id = %s LIMIT 1", [user_id])
        return cur.fetchone() is not None


def seed_demo(conn: Any, user_id: str = "u1") -> None:
    if already_seeded(conn, user_id):
        return
    ledger = ledger_for(conn)
    sarah = _insert_person(conn, user_id, _SARAH)
    marcus = _insert_person(conn, user_id, _MARCUS)
    sid = str(sarah)

    def w(
        kind: str,
        patch: dict[str, Any],
        *,
        layer: str,
        source_id: str,
        field: str | None = None,
        quote: str | None = None,
        conf: float = 1.0,
        row: str = sid,
    ) -> Any:
        return ledger.write_intent(
            user_id=user_id, kind=kind, target_entity="person", patch_json=patch,
            source_layer=layer, source_table="chat_message", source_id=source_id,
            target_row_id=row, target_field=field, source_quote=quote, confidence=conf,
        )

    # 断言基础事实 (provenance) —— 低危, auto-applied
    w("ASSERT", {"role": "senior PM", "employer": "Acme Corp"},
      layer="L2_CHAT", source_id="seed-1", quote="senior PM at Acme Corp", conf=0.92)
    # employer: Acme (高危 PATCH → 确认)
    r1 = w("PATCH", {"employer": "Acme"}, field="employer", layer="AGENT_INFERENCE",
           source_id="seed-2", quote="she just started at Acme", conf=0.9)
    ledger.confirm(user_id, [r1.intent_id])
    # 注释
    w("ANNOTATE", {"annotation": "juggling two roles, may be slow to reply"},
      layer="L2_CHAT", source_id="seed-3", quote="she's juggling two roles right now", conf=0.95)
    # employer: Globex (确认 → supersede Acme)
    r2 = w("PATCH", {"employer": "Globex"}, field="employer", layer="AGENT_INFERENCE",
           source_id="seed-4", quote="she moved to Globex", conf=0.93)
    ledger.confirm(user_id, [r2.intent_id])
    # location: Berlin 低置信改动 + FLAG → 改动被拒 (仍 SF), FLAG 留存
    r3 = w("PATCH", {"location": "Berlin"}, field="location", layer="AGENT_INFERENCE",
           source_id="seed-5", quote="I think she relocated to Berlin", conf=0.55)
    w("FLAG", {"flag_reason": "unconfirmed relocation"}, field="location",
      layer="AGENT_INFERENCE", source_id="seed-6", quote="I think she relocated to Berlin",
      conf=0.55)
    ledger.reject(user_id, [r3.intent_id], reason="user said she stays in SF")

    # 第二个联系人: 一条断言, 让列表不孤单
    w("ASSERT", {"relationship": "met at a design conference"}, layer="L2_CHAT",
      source_id="seed-m1", quote="we met at a design conference", conf=0.9, row=str(marcus))
