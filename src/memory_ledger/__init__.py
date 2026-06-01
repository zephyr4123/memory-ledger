"""memory-ledger — deterministic, provenance-first, append-only memory for LLM agents.

Typed intents instead of embeddings, as-of time-travel, and a human-confirmation
gate for risky writes — all on Postgres.

架构 (六边形 / 端口与适配器, 依赖单向 interface → application → ports ← infrastructure,
domain 不依赖任何层):

    domain/         纯业务核心 (intents / policies / snapshot)
    application/    用例编排 (MemoryLedger, SnapshotCache)
    ports/          抽象接口 (DBAdapter, IntentRepository)
    infrastructure/ 具体适配器 (PsycopgAdapter, PostgresIntentRepository, schema)
    interface/      入口 (CLI)
    bootstrap.py    组合根 (open_postgres 接线)

本模块是 facade: 内部深分层, 对外只暴露这一层浅 API.

Quickstart::

    import psycopg
    from memory_ledger import open_postgres, AutoApplyPolicy, apply_schema, PsycopgAdapter

    conn = psycopg.connect(DSN, autocommit=True)
    apply_schema(PsycopgAdapter(conn))                 # dev only; 生产用迁移工具
    ledger = open_postgres(conn, auto_apply=AutoApplyPolicy.low_risk_for(["todo_item"]))

    ledger.insert_intent(
        user_id="u1", kind="PATCH", target_entity="todo_item",
        target_row_id="42", target_field="due_date",
        patch_json={"due_date": "2026-05-30"},
        source_layer="L2_CHAT", source_table="chat_message",
        source_id="msg_001", source_quote="把买菜改成周五到期", confidence=0.95,
    )
    todo = ledger.effective("todo_item", "u1", 42)
"""

from __future__ import annotations

# ── application (用例) ──────────────────────────────────────────────
from .application import MemoryLedger, SnapshotCache
from .application.agent_loop import AgentLoop, Banner, TurnResult
from .application.ledger import WriteResult

# ── 组合根 ──────────────────────────────────────────────────────────
from .bootstrap import open_postgres

# ── domain (业务核心) ───────────────────────────────────────────────
from .domain.conversation import ProposedIntent, Response
from .domain.intents import (
    KINDS,
    SOURCE_LAYERS,
    IntentRecord,
    IntentShapeError,
    Kind,
    SourceLayer,
    normalize_intent,
    validate_intent_shape,
)
from .domain.policies import DEFAULT_THRESHOLD, AutoApplyPolicy
from .domain.snapshot import render_snapshot, sanitize_text

# ── infrastructure (适配器) ─────────────────────────────────────────
from .infrastructure.persistence import (
    PostgresIntentRepository,
    PsycopgAdapter,
    apply_schema,
    bundled_sql,
)
from .infrastructure.persistence.schema import CRM_MIGRATIONS, DEFAULT_MIGRATIONS

# ── ports (抽象) ────────────────────────────────────────────────────
from .ports import DBAdapter, InsertOutcome, IntentRepository, Row
from .ports.repository import UnknownEntityError
from .ports.responder import Responder

__version__ = "0.1.0"

__all__ = [
    "CRM_MIGRATIONS",
    "DEFAULT_MIGRATIONS",
    "DEFAULT_THRESHOLD",
    "KINDS",
    "SOURCE_LAYERS",
    "AgentLoop",
    "AutoApplyPolicy",
    "Banner",
    "DBAdapter",
    "InsertOutcome",
    "IntentRecord",
    "IntentRepository",
    "IntentShapeError",
    "Kind",
    "MemoryLedger",
    "PostgresIntentRepository",
    "ProposedIntent",
    "PsycopgAdapter",
    "Responder",
    "Response",
    "Row",
    "SnapshotCache",
    "SourceLayer",
    "TurnResult",
    "UnknownEntityError",
    "WriteResult",
    "__version__",
    "apply_schema",
    "bundled_sql",
    "normalize_intent",
    "open_postgres",
    "render_snapshot",
    "sanitize_text",
    "validate_intent_shape",
]
