"""HTTP 边界的 Pydantic 模型 + 从账本 Row(dict) 的转换器.

库返回的是 Row=dict[str,Any](DB 列名 → 值); 这里把它收口成稳定的对外 JSON 契约,
并做类型规整 (confidence Decimal→float, JSONB→list/dict 已由 psycopg 解析好)。
"""

from __future__ import annotations

from datetime import datetime
from typing import Any

from memory_ledger import Row
from pydantic import BaseModel


# ── requests ─────────────────────────────────────────────────────────
class TurnRequest(BaseModel):
    utterance: str
    person_id: int


class ConfirmRequest(BaseModel):
    intent_ids: list[int]


class RejectRequest(BaseModel):
    intent_ids: list[int]
    reason: str = ""


# ── responses ────────────────────────────────────────────────────────
class HealthOut(BaseModel):
    status: str
    llm: str  # "live" | "mock"
    model: str | None = None


class PersonListItem(BaseModel):
    id: int
    full_name: str | None = None
    employer: str | None = None
    role: str | None = None
    location: str | None = None


class PersonOut(BaseModel):
    """某 person 截至 as_of 的合成真相 + 溯源聚合 (assertions/annotations/flags)。"""

    id: int
    full_name: str | None = None
    employer: str | None = None
    role: str | None = None
    location: str | None = None
    comm_pref: str | None = None
    relationship: str | None = None
    assertions: list[dict[str, Any]] = []
    annotations: list[dict[str, Any]] = []
    flags: list[dict[str, Any]] = []
    intents_applied_as_of: list[int] = []
    as_of: datetime | None = None

    @classmethod
    def from_effective(cls, row: Row, *, as_of: datetime | None = None) -> PersonOut:
        return cls(
            id=int(row["id"]),
            full_name=row.get("full_name_eff"),
            employer=row.get("employer_eff"),
            role=row.get("role_eff"),
            location=row.get("location_eff"),
            comm_pref=row.get("comm_pref_eff"),
            relationship=row.get("relationship_eff"),
            assertions=list(row.get("assertions") or []),
            annotations=list(row.get("annotations") or []),
            flags=list(row.get("flags") or []),
            intents_applied_as_of=[int(i) for i in (row.get("intents_applied_as_of") or [])],
            as_of=as_of,
        )


class LedgerEventOut(BaseModel):
    """一条原始 intent (账本时间轴 + 逐字溯源用)。"""

    id: int
    kind: str
    status: str
    target_field: str | None = None
    patch_json: dict[str, Any] = {}
    source_layer: str
    source_priority: int | None = None
    source_quote: str | None = None
    confidence: float
    reason: str = ""
    applied_at: datetime | None = None
    superseded_by: int | None = None
    rejected_at: datetime | None = None
    rejected_reason: str | None = None
    expired_at: datetime | None = None
    created_at: datetime

    @classmethod
    def from_row(cls, row: Row) -> LedgerEventOut:
        return cls(
            id=int(row["id"]),
            kind=row["kind"],
            status=row["status"],
            target_field=row.get("target_field"),
            patch_json=dict(row.get("patch_json") or {}),
            source_layer=row["source_layer"],
            source_priority=(
                int(row["source_priority"]) if row.get("source_priority") is not None else None
            ),
            source_quote=row.get("source_quote"),
            confidence=float(row["confidence"]),
            reason=row.get("reason") or "",
            applied_at=row.get("applied_at"),
            superseded_by=(
                int(row["superseded_by"]) if row.get("superseded_by") is not None else None
            ),
            rejected_at=row.get("rejected_at"),
            rejected_reason=row.get("rejected_reason"),
            expired_at=row.get("expired_at"),
            created_at=row["created_at"],
        )


class BannerOut(BaseModel):
    """一条待人工确认的高危改动 (PROPOSED PATCH)。"""

    intent_id: int
    target_field: str | None = None
    proposed_value: Any = None
    confidence: float


class TransitionResult(BaseModel):
    affected: int
