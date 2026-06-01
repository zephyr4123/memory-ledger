"""小本的工具集 —— 少而全的几把"胖刀", 全经 @tool 注册。

读工具(自主调, 返回数据回灌模型):
  * list_contacts(query?)            —— 名册 + 模糊搜索, 一把看"我认识谁"
  * get_contact(id, as_of?, include?) —— 核心胖刀: 一个人的全貌(当前字段 + 溯源 + 历史 + 时点回看)
  * review_open_items(contact_id?)   —— 跨人汇总"要你确认的 / 拿不准的"

写工具(暂存, 待路由落盘走确认闸门):
  * record_memory_intents(intents)   —— 记/改/标记; 改既有字段→PATCH 走闸门, 未知字段→明确拒绝不静默吞

字段是固定集合 (person 实体), 所以"陈述某字段的事实"= 改该字段 = PATCH —— 写工具据此把
打到结构化字段的 ASSERT 纠正成 PATCH(修旧缺陷: ASSERT 绕过闸门 + 静默不更新人卡)。
"""

from __future__ import annotations

from datetime import datetime
from typing import Any

from memory_ledger import ProposedIntent

from .context import ToolContext
from .registry import tool

# person 的可改字段全集 (与 004_person.sql 列对齐)。打到这些之外的字段一律明确拒绝。
PERSON_FIELDS: tuple[str, ...] = (
    "full_name",
    "employer",
    "role",
    "location",
    "comm_pref",
    "relationship",
)
TOOL_NAME = "record_memory_intents"

_FIELD_CN = {
    "full_name": "姓名",
    "employer": "公司",
    "role": "职位",
    "location": "在哪",
    "comm_pref": "怎么联系",
    "relationship": "关系",
}


def _clamp(x: float) -> float:
    return 0.0 if x < 0 else 1.0 if x > 1 else x


def _parse_as_of(s: str | None) -> datetime | None:
    if not s:
        return None
    try:
        return datetime.fromisoformat(s.replace("Z", "+00:00"))
    except (ValueError, TypeError):
        return None


def _person_ids(ctx: ToolContext) -> list[int]:
    with ctx.conn.cursor() as cur:
        cur.execute(
            "SELECT id FROM person WHERE user_id = %s AND deleted = false ORDER BY id",
            [ctx.user_id],
        )
        return [int(r[0]) for r in cur.fetchall()]


def _brief(ctx: ToolContext, pid: int, eff: Any = None) -> dict[str, Any] | None:
    eff = eff if eff is not None else ctx.ledger.effective("person", ctx.user_id, pid)
    if eff is None:
        return None
    return {
        "id": pid,
        "name": eff.get("full_name_eff"),
        "employer": eff.get("employer_eff"),
        "role": eff.get("role_eff"),
        "location": eff.get("location_eff"),
    }


# ─────────────────────────────── 读工具 ───────────────────────────────
@tool(
    name="list_contacts",
    description=(
        "列出/搜索用户的联系人。想知道'我认识谁'、或按名字/公司/职位找某个人时用。"
        "query 留空=返回全部;带词=按名字/公司/职位/所在地模糊筛选。"
    ),
    parameters={
        "type": "object",
        "properties": {
            "query": {
                "type": "string",
                "description": "模糊筛选词(匹配名字/公司/职位/所在地);留空返回全部",
            }
        },
        "required": [],
    },
)
def list_contacts(ctx: ToolContext, query: str | None = None) -> dict[str, Any]:
    rows = [b for pid in _person_ids(ctx) if (b := _brief(ctx, pid)) is not None]
    if query:
        q = query.strip().lower()
        rows = [
            b
            for b in rows
            if any(q in str(b.get(k) or "").lower() for k in ("name", "employer", "role", "location"))
        ]
    return {"count": len(rows), "contacts": rows}


@tool(
    name="get_contact",
    description=(
        "查看一个联系人的全貌:当前所有字段 + 溯源(每条事实的逐字原话与把握程度) + 拿不准的标记。"
        "回答关于某人的问题前应先调它看清现状。as_of 传 ISO 时间可回看'那时候 TA 是什么样'(时光机);"
        "include 可加 'history' 看完整变更史(谁、什么时候、从哪听来、改了什么)。"
    ),
    parameters={
        "type": "object",
        "properties": {
            "contact_id": {"type": "integer", "description": "联系人 id(来自 list_contacts)"},
            "as_of": {
                "type": "string",
                "description": "ISO 时间, 回看该时点的真相;留空=现在",
            },
            "include": {
                "type": "array",
                "items": {"type": "string", "enum": ["facts", "notes", "flags", "history"]},
                "description": "额外带哪些;默认 facts+notes+flags(history 较长, 需要时再要)",
            },
        },
        "required": ["contact_id"],
    },
)
def get_contact(
    ctx: ToolContext,
    contact_id: int,
    as_of: str | None = None,
    include: list[str] | None = None,
) -> dict[str, Any]:
    inc = set(include) if include else {"facts", "notes", "flags"}
    eff = ctx.ledger.effective("person", ctx.user_id, int(contact_id), as_of=_parse_as_of(as_of))
    if eff is None:
        return {"error": f"没有 id={contact_id} 这个联系人"}
    out: dict[str, Any] = {
        "id": int(eff["id"]),
        "as_of": as_of or "现在",
        "fields": {
            "name": eff.get("full_name_eff"),
            "employer": eff.get("employer_eff"),
            "role": eff.get("role_eff"),
            "location": eff.get("location_eff"),
            "comm_pref": eff.get("comm_pref_eff"),
            "relationship": eff.get("relationship_eff"),
        },
    }
    if "facts" in inc:
        out["facts"] = [
            {"原话": a.get("source_quote"), "把握": a.get("confidence"), "内容": a.get("payload")}
            for a in (eff.get("assertions") or [])
        ]
    if "notes" in inc:
        out["notes"] = [n.get("annotation") for n in (eff.get("annotations") or [])]
    if "flags" in inc:
        out["flags"] = [
            {"字段": f.get("target_field"), "拿不准": f.get("flag_reason")}
            for f in (eff.get("flags") or [])
        ]
    if "history" in inc:
        out["history"] = [
            _event_brief(r) for r in ctx.ledger.history("person", ctx.user_id, int(contact_id))
        ]
    return out


def _event_brief(r: Any) -> dict[str, Any]:
    field = r.get("target_field")
    patch = r.get("patch_json") or {}
    if r["kind"] == "PATCH":
        summary = f"{field} → {patch.get(field)}"
    elif r["kind"] == "ANNOTATE":
        summary = str(patch.get("annotation"))
    elif r["kind"] == "FLAG":
        summary = f"{field}: {patch.get('flag_reason')}"
    else:  # ASSERT
        summary = ", ".join(f"{k}={v}" for k, v in patch.items())
    return {
        "kind": r["kind"],
        "status": r["status"],
        "summary": summary,
        "原话": r.get("source_quote"),
        "把握": float(r["confidence"]),
        "来源": r.get("source_layer"),
        "when": (r.get("applied_at") or r.get("created_at")).isoformat()
        if (r.get("applied_at") or r.get("created_at"))
        else None,
        "id": int(r["id"]),
    }


@tool(
    name="review_open_items",
    description=(
        "汇总需要用户处理的事:还'等你点头'的待确认改动(PROPOSED)+ 各人身上'拿不准'的标记(FLAG)。"
        "用户问'有啥要我确认的/还有哪些没定'时用。contact_id 留空=查所有人。"
    ),
    parameters={
        "type": "object",
        "properties": {
            "contact_id": {"type": "integer", "description": "只看某人;留空=所有联系人"}
        },
        "required": [],
    },
)
def review_open_items(ctx: ToolContext, contact_id: int | None = None) -> dict[str, Any]:
    ids = [int(contact_id)] if contact_id else _person_ids(ctx)
    pending: list[dict[str, Any]] = []
    flags: list[dict[str, Any]] = []
    for pid in ids:
        b = _brief(ctx, pid)
        name = b["name"] if b else None
        for r in ctx.ledger.history("person", ctx.user_id, pid, statuses=["PROPOSED"]):
            ev = _event_brief(r)
            pending.append({"contact_id": pid, "contact": name, "intent_id": ev["id"], "改动": ev["summary"], "原话": ev["原话"], "把握": ev["把握"]})
        eff = ctx.ledger.effective("person", ctx.user_id, pid)
        for f in (eff.get("flags") if eff else []) or []:
            flags.append({"contact_id": pid, "contact": name, "字段": f.get("target_field"), "拿不准": f.get("flag_reason")})
    return {"待确认": pending, "拿不准": flags, "待确认数": len(pending), "拿不准数": len(flags)}


# ─────────────────────────────── 写工具 ───────────────────────────────
def _stage(raw_intents: list[Any], person_id: int) -> tuple[list[ProposedIntent], list[str]]:
    """把模型吐的 intent 映射成 ProposedIntent 并暂存; 返回 (待写, 给用户的说明)。

    纠错: 打到结构化字段的 ASSERT → 改成 PATCH(走闸门 + 真正更新人卡);
    未知字段的 PATCH/ASSERT/FLAG → 明确拒绝并写进说明(不再静默吞掉合法改动)。
    """
    staged: list[ProposedIntent] = []
    errs: list[str] = []

    def patch(field: str, value: Any, quote: str | None, conf: float) -> None:
        staged.append(
            ProposedIntent(
                kind="PATCH", target_entity="person", patch_json={field: value},
                target_row_id=str(person_id), target_field=field,
                source_quote=quote, confidence=conf,
            )
        )

    for it in raw_intents or []:
        if not isinstance(it, dict):
            continue
        kind = it.get("kind")
        quote = it.get("source_quote")
        try:
            conf = _clamp(float(it.get("confidence", 0.8)))
        except (TypeError, ValueError):
            conf = 0.8

        if kind == "ASSERT":
            assertion = it.get("assertion")
            if not isinstance(assertion, dict) or not assertion:
                continue
            for k, v in assertion.items():
                if k in PERSON_FIELDS:
                    patch(k, v, quote, conf)  # 结构化字段 → 当改动处理, 走闸门
                else:
                    errs.append(f"「{k}」这个字段我没有, 没记")
        elif kind == "PATCH":
            field = it.get("target_field")
            val = it.get("value")
            if not field or val is None:
                continue
            if field not in PERSON_FIELDS:
                errs.append(f"「{field}」这个字段我没有, 没法改")
                continue
            patch(field, val, quote, conf)
        elif kind == "ANNOTATE":
            note = it.get("annotation")
            if note:
                staged.append(
                    ProposedIntent(
                        kind="ANNOTATE", target_entity="person", patch_json={"annotation": note},
                        target_row_id=str(person_id), target_field=None,
                        source_quote=quote, confidence=conf,
                    )
                )
        elif kind == "FLAG":
            field = it.get("target_field")
            reason = it.get("flag_reason")
            if not field or not reason:
                continue
            if field not in PERSON_FIELDS:
                errs.append(f"「{field}」这个字段我没有, 标不了")
                continue
            staged.append(
                ProposedIntent(
                    kind="FLAG", target_entity="person", patch_json={"flag_reason": reason},
                    target_row_id=str(person_id), target_field=field,
                    source_quote=quote, confidence=conf,
                )
            )
    return staged, errs


@tool(
    name=TOOL_NAME,
    description=(
        "记录从用户这句话里得到的记忆改动。用户陈述/更改/标注/质疑某联系人的事实时调它, 一条事实一项。"
        "改既有字段(公司/职位/在哪/怎么联系/姓名/关系)用 PATCH(高危, 会停在确认闸门等用户点头);"
        "随手备注用 ANNOTATE;拿不准用 FLAG。每项带 source_quote=用户原话、confidence=0-1 把握。"
    ),
    parameters={
        "type": "object",
        "properties": {
            "intents": {
                "type": "array",
                "items": {
                    "type": "object",
                    "properties": {
                        "kind": {
                            "type": "string",
                            "enum": ["PATCH", "ASSERT", "ANNOTATE", "FLAG"],
                            "description": "PATCH=改既有字段(高危需确认);ASSERT=陈述事实;ANNOTATE=备注;FLAG=标记拿不准",
                        },
                        "target_field": {
                            "type": "string",
                            "description": "PATCH/FLAG 用: full_name|employer|role|location|comm_pref|relationship 之一",
                        },
                        "value": {"type": "string", "description": "PATCH 用: 该字段的新值"},
                        "assertion": {"type": "object", "description": "ASSERT 用: {字段: 值}"},
                        "annotation": {"type": "string", "description": "ANNOTATE 用: 备注文本"},
                        "flag_reason": {"type": "string", "description": "FLAG 用: 为什么拿不准"},
                        "source_quote": {"type": "string", "description": "用户的原话, 逐字"},
                        "confidence": {"type": "number", "description": "0-1 的把握程度"},
                    },
                    "required": ["kind"],
                },
            }
        },
        "required": ["intents"],
    },
)
def record_memory_intents(ctx: ToolContext, intents: list[Any] | None = None) -> dict[str, Any]:
    staged, errs = _stage(intents or [], ctx.focus_person_id)
    ctx.staged_intents.extend(staged)
    parts: list[str] = []
    if staged:
        parts.append(f"记下了 {len(staged)} 条(改动会停在确认闸门, 等用户点头)")
    parts.extend(errs)
    return {
        "ok": True,
        "staged": len(staged),
        "message": ";".join(parts) if parts else "这句里没有需要记的改动",
    }
