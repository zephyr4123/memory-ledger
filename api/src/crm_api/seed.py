"""启动时确定性预置 demo 数据 —— 让时光机/溯源/账本开箱即有料 (中文冷启动语料).

通过 ledger API(write_intent + confirm/reject)按真实生命周期构造 林思颖 的账本史:
  雇主 晨星科技(raw) → 蓝湖科技(确认) → Globex(确认, supersede 蓝湖);
  location 一次低置信"柏林"改动被**拒绝**(仍上海)并留一条 FLAG; 另含注释/断言。
另置一个联系人 赵明轩 填充列表。幂等: 已有该用户的 person 行则跳过。

注意: 这是 demo fixture, 不是产品逻辑。真实改动一律来自对话里的真 LLM。
"""

from __future__ import annotations

from typing import Any

from .db import ledger_for

_SARAH = {
    "full_name": "林思颖",
    "employer": "晨星科技",
    "role": "产品经理",
    "location": "上海",
    "comm_pref": "email",  # CHECK 约束: 仅 email/phone/sms; 展示层映射成中文
}
_MARCUS = {
    "full_name": "赵明轩",
    "employer": "翰墨设计",
    "role": "设计师",
    "location": "成都",
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
    w("ASSERT", {"role": "资深产品经理", "employer": "晨星科技"},
      layer="L2_CHAT", source_id="seed-1", quote="她是晨星科技的资深产品经理", conf=0.92)
    # employer: 蓝湖科技 (高危 PATCH → 确认)
    r1 = w("PATCH", {"employer": "蓝湖科技"}, field="employer", layer="AGENT_INFERENCE",
           source_id="seed-2", quote="她最近跳槽去了蓝湖科技", conf=0.9)
    ledger.confirm(user_id, [r1.intent_id])
    # 注释
    w("ANNOTATE", {"annotation": "同时兼着两个角色，回复可能会慢"},
      layer="L2_CHAT", source_id="seed-3", quote="她现在同时扛着两个角色，回得有点慢", conf=0.95)
    # employer: Globex (确认 → supersede 蓝湖科技)
    r2 = w("PATCH", {"employer": "Globex"}, field="employer", layer="AGENT_INFERENCE",
           source_id="seed-4", quote="她又跳到 Globex 了", conf=0.93)
    ledger.confirm(user_id, [r2.intent_id])
    # location: 柏林 低置信改动 + FLAG → 改动被拒 (仍上海), FLAG 留存
    r3 = w("PATCH", {"location": "柏林"}, field="location", layer="AGENT_INFERENCE",
           source_id="seed-5", quote="我猜她是不是搬去柏林了？", conf=0.55)
    # FLAG 置信度需 ≥ 阈值(0.6)才 auto-apply: 0.7 = "确信此字段该标疑"
    w("FLAG", {"flag_reason": "搬迁尚未确认"}, field="location",
      layer="AGENT_INFERENCE", source_id="seed-6", quote="我猜她是不是搬去柏林了？",
      conf=0.7)
    ledger.reject(user_id, [r3.intent_id], reason="她说她还在上海")

    # 第二个联系人: 一条断言, 让列表不孤单
    w("ASSERT", {"relationship": "在一次设计大会上认识"}, layer="L2_CHAT",
      source_id="seed-m1", quote="我们是在一次设计大会上认识的", conf=0.9, row=str(marcus))
