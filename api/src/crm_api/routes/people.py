"""/api/people —— 联系人列表 + as-of 真相 + 账本流水 (时光机/溯源的读侧)。"""

from __future__ import annotations

from datetime import datetime
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Query

from ..config import Settings
from ..db import ledger_for
from ..deps import get_conn, get_settings
from ..schemas import LedgerEventOut, PersonListItem, PersonOut

router = APIRouter()


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
