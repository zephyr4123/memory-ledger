"""/api/people —— 联系人列表 + as-of 真相 + 账本流水 (时光机/溯源的读侧)。"""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Query

from .. import conversations as store
from ..config import Settings
from ..db import ledger_for
from ..deps import get_conn, get_settings
from ..policy import VALUE_ALIASES
from ..schemas import (
    CreatePersonRequest,
    LedgerEventOut,
    PersonListItem,
    PersonOut,
    UpdatePersonRequest,
)

router = APIRouter()

# person 的可写字段全集 (与 004_person.sql 对齐); full_name 是 NOT NULL 的身份。
PERSON_FIELDS: tuple[str, ...] = (
    "full_name", "employer", "role", "location", "comm_pref", "relationship",
)
_COMM_OK = {"email", "phone", "sms"}


def _norm_comm(value: str) -> str:
    """把 comm_pref 归一到 canonical enum (中文/口语 → email/phone/sms); 非法值抛 422。"""
    v = VALUE_ALIASES["comm_pref"].get(value.strip(), value.strip().lower())
    if v not in _COMM_OK:
        raise HTTPException(status_code=422, detail="comm_pref 只能是 邮件/电话/短信")
    return v


def _clean_fields(body: Any) -> dict[str, str]:
    """取出请求里非空的可写字段, comm_pref 归一。"""
    out: dict[str, str] = {}
    for f in PERSON_FIELDS:
        raw = getattr(body, f, None)
        if raw is None:
            continue
        val = str(raw).strip()
        if not val:
            continue
        out[f] = _norm_comm(val) if f == "comm_pref" else val
    return out


@router.get("/people", response_model=list[PersonListItem])
def list_people(
    conn: Any = Depends(get_conn),
    settings: Settings = Depends(get_settings),
) -> list[PersonListItem]:
    ledger = ledger_for(conn)
    with conn.cursor() as cur:
        cur.execute(
            "SELECT id FROM person WHERE user_id = %s AND deleted = false ORDER BY id",
            [settings.user_id],
        )
        ids = [int(r[0]) for r in cur.fetchall()]
    out: list[PersonListItem] = []
    for pid in ids:
        eff = ledger.effective("person", settings.user_id, pid)
        if eff is None:
            continue
        out.append(
            PersonListItem(
                id=pid,
                full_name=eff.get("full_name_eff"),
                employer=eff.get("employer_eff"),
                role=eff.get("role_eff"),
                location=eff.get("location_eff"),
            )
        )
    return out


@router.get("/people/{person_id}", response_model=PersonOut)
def get_person(
    person_id: int,
    as_of: datetime | None = Query(default=None),
    conn: Any = Depends(get_conn),
    settings: Settings = Depends(get_settings),
) -> PersonOut:
    """某联系人截至 as_of(缺省=现在)的合成真相 —— 时光机的核心读。"""
    eff = ledger_for(conn).effective("person", settings.user_id, person_id, as_of=as_of)
    if eff is None:
        raise HTTPException(status_code=404, detail="person not found")
    return PersonOut.from_effective(eff, as_of=as_of)


@router.get("/people/{person_id}/ledger", response_model=list[LedgerEventOut])
def get_ledger_history(
    person_id: int,
    conn: Any = Depends(get_conn),
    settings: Settings = Depends(get_settings),
) -> list[LedgerEventOut]:
    """原始 intent 流水 (审计时间轴 + 逐字溯源), 按时间升序。"""
    rows = ledger_for(conn).history("person", settings.user_id, person_id)
    return [LedgerEventOut.from_row(r) for r in rows]


# ── 联系人 CRUD 的写侧 ─────────────────────────────────────────────────
@router.post("/people", response_model=PersonOut)
def create_person(
    body: CreatePersonRequest,
    conn: Any = Depends(get_conn),
    settings: Settings = Depends(get_settings),
) -> PersonOut:
    """新建联系人 —— 基础资料即"原始事实"层 (无需走账本/闸门), 直接落 person 行。"""
    cols = _clean_fields(body)
    if not cols.get("full_name"):
        raise HTTPException(status_code=422, detail="full_name 必填")
    keys = ["user_id", *cols.keys()]
    vals = [settings.user_id, *cols.values()]
    placeholders = ", ".join(["%s"] * len(vals))
    with conn.cursor() as cur:
        cur.execute(
            f"INSERT INTO person ({', '.join(keys)}) VALUES ({placeholders}) RETURNING id",
            vals,
        )
        pid = int(cur.fetchone()[0])
    eff = ledger_for(conn).effective("person", settings.user_id, pid)
    if eff is None:  # pragma: no cover — 刚插入必能读到
        raise HTTPException(status_code=500, detail="created but not readable")
    return PersonOut.from_effective(eff)


@router.patch("/people/{person_id}", response_model=PersonOut)
def update_person(
    person_id: int,
    body: UpdatePersonRequest,
    conn: Any = Depends(get_conn),
    settings: Settings = Depends(get_settings),
) -> PersonOut:
    """编辑联系人字段 —— 走账本: 每个改的字段写一条 USER_DIRECT 的 PATCH 并即时确认。

    USER_DIRECT 优先级最高(压过 agent 的猜测), 所以一定真生效; 同时留痕可溯源
    (在"记过的事"里显示为"你直接改的")。
    """
    uid = settings.user_id
    ledger = ledger_for(conn)
    if ledger.effective("person", uid, person_id) is None:
        raise HTTPException(status_code=404, detail="person not found")
    source_id = f"edit-{uuid.uuid4().hex[:12]}"
    for field, value in _clean_fields(body).items():
        res = ledger.write_intent(
            user_id=uid, kind="PATCH", target_entity="person",
            patch_json={field: value}, source_layer="USER_DIRECT",
            source_table="person_edit", source_id=source_id,
            target_row_id=str(person_id), target_field=field,
            source_quote=None, confidence=1.0,
        )
        if res.intent_id is not None and not res.applied:
            ledger.confirm(uid, [res.intent_id])
    eff = ledger.effective("person", uid, person_id)
    if eff is None:  # pragma: no cover
        raise HTTPException(status_code=404, detail="person not found")
    return PersonOut.from_effective(eff)


@router.delete("/people/{person_id}")
def delete_person(
    person_id: int,
    conn: Any = Depends(get_conn),
    settings: Settings = Depends(get_settings),
) -> dict[str, Any]:
    """删除联系人 —— 一并清掉 TA 名下全部账本记忆 + 悬空的线程焦点, 不留僵尸。原子。"""
    uid = settings.user_id
    ledger = ledger_for(conn)
    if ledger.effective("person", uid, person_id) is None:
        raise HTTPException(status_code=404, detail="person not found")
    # 三步一事务: 抹账本记忆 + 清线程焦点 + 硬删 person 行 (全有或全无)。
    prev_autocommit = getattr(conn, "autocommit", True)
    try:
        conn.autocommit = False
        with conn.transaction():
            purged = ledger.purge_row("person", uid, person_id)
            store.clear_focus(conn, uid, person_id)
            with conn.cursor() as cur:
                cur.execute(
                    "DELETE FROM person WHERE id = %s AND user_id = %s", [person_id, uid]
                )
    finally:
        conn.autocommit = prev_autocommit
    return {"ok": True, "purged_intents": purged}
