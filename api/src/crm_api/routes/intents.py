"""/api/intents —— 人工确认闸门的两个动作: confirm / reject。"""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends

from ..config import Settings
from ..db import ledger_for
from ..deps import get_conn, get_settings
from ..schemas import ConfirmRequest, RejectRequest, TransitionResult

router = APIRouter()


@router.post("/intents/confirm", response_model=TransitionResult)
def confirm(
    body: ConfirmRequest,
    conn: Any = Depends(get_conn),
    settings: Settings = Depends(get_settings),
) -> TransitionResult:
    n = ledger_for(conn).confirm(settings.user_id, body.intent_ids)
    return TransitionResult(affected=n)


@router.post("/intents/reject", response_model=TransitionResult)
def reject(
    body: RejectRequest,
    conn: Any = Depends(get_conn),
    settings: Settings = Depends(get_settings),
) -> TransitionResult:
    n = ledger_for(conn).reject(settings.user_id, body.intent_ids, body.reason)
    return TransitionResult(affected=n)
