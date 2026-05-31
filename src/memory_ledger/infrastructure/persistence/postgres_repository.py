"""PostgresIntentRepository —— IntentRepository 端口的 Postgres 实现.

本模块是账本所有 SQL、advisory-lock 串行化、auto-supersede 时序的唯一归属地.
它通过 DBAdapter 端口跑 SQL, 因此天然支持换驱动 (psycopg / asyncpg-sync-wrap /
SQLAlchemy core) 而 SQL 复用 (都是 Postgres SQL).

关键正确性保证 (对应已修复缺陷, 见 sql/001_core.sql 与测试):
  * 多租户: effective_<entity>_at 必传 p_user_id, 越权读不到.
  * 单一时钟源: applied_at / rejected_at / expired_at 一律 DB clock_timestamp().
  * 幂等: 同 source 的同 (entity,row,field,kind) 复用既有 id (pre-SELECT + 唯一索引兜底).
  * 并发: PATCH 写前对 (user,entity,row,field) 取 pg_advisory_xact_lock 串行.
  * EXPIRED 真落地: expired_at 列 + effective view 按 as_of 比较.
"""

from __future__ import annotations

import re
from collections.abc import Sequence
from datetime import datetime
from typing import Any

from ...domain.intents import IntentRecord
from ...ports.database import DBAdapter, Row
from ...ports.repository import InsertOutcome
from .serialization import to_jsonb

# entity 名会被拼进 effective_<entity>_at 函数名, 必须是合法标识符 (防注入).
_IDENT = re.compile(r"^[a-z_][a-z0-9_]*$")


def _lock_key(user_id: str, entity: str, row_id: str | None, field: str | None) -> str:
    return f"{user_id}|{entity}|{row_id or ''}|{field or ''}"


class PostgresIntentRepository:
    """把 DBAdapter 包装成账本持久化端口."""

    def __init__(self, db: DBAdapter) -> None:
        self.db = db

    # ── write ────────────────────────────────────────────────────────
    def insert(self, record: IntentRecord, *, auto_apply: bool) -> InsertOutcome:
        r = record
        needs_lock = r.kind == "PATCH" and auto_apply
        with self.db.transaction() as tx:
            if needs_lock:
                tx.execute(
                    "SELECT pg_advisory_xact_lock(hashtext(%s))",
                    [_lock_key(r.user_id, r.target_entity, r.target_row_id, r.target_field)],
                )

            existing = tx.fetchone(
                """
                SELECT id FROM l15_change_intents
                WHERE user_id = %s AND source_table = %s AND source_id = %s
                  AND target_entity = %s
                  AND COALESCE(target_row_id,'') = COALESCE(%s,'')
                  AND COALESCE(target_field,'')  = COALESCE(%s,'')
                  AND kind = %s
                  AND status <> 'REJECTED'
                LIMIT 1
                """,
                [
                    r.user_id, r.source_table, r.source_id, r.target_entity,
                    r.target_row_id, r.target_field, r.kind,
                ],
            )
            if existing:
                return InsertOutcome(int(existing["id"]), created=False)

            row = tx.fetchone(
                """
                INSERT INTO l15_change_intents (
                    user_id, kind, target_entity, target_date, target_row_id,
                    target_field, patch_json, reason, source_layer, source_table,
                    source_id, source_quote, extracted_by, confidence,
                    status, applied_at
                ) VALUES (
                    %s, %s, %s, %s, %s,
                    %s, %s::jsonb, %s, %s, %s,
                    %s, %s, %s, %s,
                    %s, CASE WHEN %s THEN clock_timestamp() ELSE NULL END
                )
                RETURNING id
                """,
                [
                    r.user_id, r.kind, r.target_entity, r.target_date, r.target_row_id,
                    r.target_field, to_jsonb(r.patch_json), r.reason, r.source_layer,
                    r.source_table, r.source_id, r.source_quote, r.extracted_by,
                    r.confidence, "APPLIED" if auto_apply else "PROPOSED", auto_apply,
                ],
            )
        assert row is not None  # INSERT ... RETURNING 必返回一行
        return InsertOutcome(int(row["id"]), created=True)

    # ── lifecycle ────────────────────────────────────────────────────
    def confirm(self, user_id: str, intent_ids: Sequence[int]) -> int:
        """PROPOSED → APPLIED, 维护"一字段一条 live PATCH"不变量.

        顺序关键: 先 supersede 同 key 的旧 live PATCH, 再把本条翻 APPLIED —— 否则
        会有"两条同时 live"的瞬间触发 uq_l15_one_live_patch 唯一索引 (不可延迟).
        """
        n = 0
        with self.db.transaction() as tx:
            targets = tx.fetchall(
                """
                SELECT id, kind, target_entity, target_row_id, target_field
                FROM l15_change_intents
                WHERE id = ANY(%s) AND user_id = %s AND status = 'PROPOSED'
                ORDER BY id
                """,
                [list(intent_ids), user_id],
            )
            for t in targets:
                if t["kind"] == "PATCH":
                    tx.execute(
                        "SELECT pg_advisory_xact_lock(hashtext(%s))",
                        [
                            _lock_key(
                                user_id, t["target_entity"],
                                t["target_row_id"], t["target_field"],
                            )
                        ],
                    )
                    tx.execute(
                        """
                        UPDATE l15_change_intents prev
                        SET superseded_by = %s, status = 'SUPERSEDED'
                        WHERE prev.user_id = %s AND prev.target_entity = %s
                          AND COALESCE(prev.target_row_id,'') = COALESCE(%s,'')
                          AND prev.target_field = %s
                          AND prev.kind = 'PATCH' AND prev.status = 'APPLIED'
                          AND prev.superseded_by IS NULL AND prev.id <> %s
                        """,
                        [
                            t["id"], user_id, t["target_entity"],
                            t["target_row_id"], t["target_field"], t["id"],
                        ],
                    )
                tx.execute(
                    """
                    UPDATE l15_change_intents
                    SET status = 'APPLIED', applied_at = clock_timestamp()
                    WHERE id = %s
                    """,
                    [t["id"]],
                )
                n += 1
        return n

    def reject(self, user_id: str, intent_ids: Sequence[int], reason: str = "") -> int:
        rows = self.db.fetchall(
            """
            UPDATE l15_change_intents
            SET status = 'REJECTED', rejected_at = clock_timestamp(), rejected_reason = %s
            WHERE id = ANY(%s) AND user_id = %s
              AND status IN ('PROPOSED', 'APPLIED')
            RETURNING id
            """,
            [reason, list(intent_ids), user_id],
        )
        return len(rows)

    def expire_before(
        self,
        cutoff: datetime,
        *,
        user_id: str | None = None,
        target_entity: str | None = None,
    ) -> list[str]:
        clauses = ["status = 'APPLIED'", "superseded_by IS NULL", "applied_at < %s"]
        params: list[Any] = [cutoff]
        if user_id is not None:
            clauses.append("user_id = %s")
            params.append(user_id)
        if target_entity is not None:
            clauses.append("target_entity = %s")
            params.append(target_entity)
        rows = self.db.fetchall(
            f"""
            UPDATE l15_change_intents
            SET status = 'EXPIRED', expired_at = clock_timestamp()
            WHERE {" AND ".join(clauses)}
            RETURNING user_id
            """,
            params,
        )
        return [str(r["user_id"]) for r in rows]

    # ── read ─────────────────────────────────────────────────────────
    def effective(
        self,
        entity: str,
        user_id: str,
        row_id: int | str,
        *,
        as_of: datetime | None = None,
    ) -> Row | None:
        if not _IDENT.match(entity):
            raise ValueError(f"invalid entity identifier: {entity!r}")
        fn = f"effective_{entity}_at"
        if as_of is None:
            return self.db.fetchone(
                f"SELECT * FROM {fn}(%s, %s, clock_timestamp())",
                [user_id, int(row_id)],
            )
        return self.db.fetchone(
            f"SELECT * FROM {fn}(%s, %s, %s)",
            [user_id, int(row_id), as_of],
        )
