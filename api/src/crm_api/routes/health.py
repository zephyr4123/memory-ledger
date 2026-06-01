"""/api/health —— 存活 + 当前 LLM 模式 (live / mock)。"""

from __future__ import annotations

from fastapi import APIRouter, Depends

from ..config import Settings
from ..deps import get_settings
from ..schemas import HealthOut

router = APIRouter()


@router.get("/health", response_model=HealthOut)
def health(settings: Settings = Depends(get_settings)) -> HealthOut:
    return HealthOut(
        status="ok",
        llm="live" if settings.llm_enabled else "mock",
        model=settings.model if settings.llm_enabled else None,
    )
