"""对话线程持久化 —— crm_api 应用层自有 (库核心与"聊天"无关, 单向依赖不破)。

两张表:
  conversation —— 一个聊天线程 (标题 / 焦点联系人 / 时间戳)。
  conv_message —— 线程里的每条消息 (role=user|agent + 正文 + 工具事件 JSON)。

记忆本体 (l15_change_intents) 仍按 user_id 全局共享 —— 不同对话查到的是同一份真相,
这正是"跨对话记忆"的来源。对话只是聊天容器, 不持有记忆。所有读写都按 user_id 收口
(多租户越权防线)。
"""

from __future__ import annotations

from typing import Any

from psycopg.rows import dict_row
from psycopg.types.json import Json

_CONV_COLS = "id, title, focus_person_id, created_at, updated_at"


def ensure_chat_schema(conn: Any) -> None:
    """幂等建对话线程表 (不动库迁移链 001-004)。"""
    with conn.cursor() as cur:
        cur.execute(
            """
            CREATE TABLE IF NOT EXISTS conversation (
                id              bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
                user_id         text NOT NULL,
                title           text NOT NULL DEFAULT '',
                focus_person_id bigint,
                created_at      timestamptz NOT NULL DEFAULT now(),
                updated_at      timestamptz NOT NULL DEFAULT now()
            )
            """
        )
        cur.execute(
            "CREATE INDEX IF NOT EXISTS ix_conversation_user "
            "ON conversation (user_id, updated_at DESC)"
        )
        cur.execute(
            """
            CREATE TABLE IF NOT EXISTS conv_message (
                id              bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
                conversation_id bigint NOT NULL
                                REFERENCES conversation (id) ON DELETE CASCADE,
                user_id         text NOT NULL,
                role            text NOT NULL CHECK (role IN ('user', 'agent')),
                content         text NOT NULL DEFAULT '',
                tools_json      jsonb NOT NULL DEFAULT '[]'::jsonb,
                created_at      timestamptz NOT NULL DEFAULT now()
            )
            """
        )
        cur.execute(
            "CREATE INDEX IF NOT EXISTS ix_conv_message_conv "
            "ON conv_message (conversation_id, id)"
        )


def _conv(row: dict[str, Any]) -> dict[str, Any]:
    return {
        "id": int(row["id"]),
        "title": row["title"],
        "focus_person_id": (
            int(row["focus_person_id"]) if row.get("focus_person_id") is not None else None
        ),
        "created_at": row["created_at"],
        "updated_at": row["updated_at"],
        "message_count": int(row.get("message_count", 0) or 0),
    }


def create_conversation(
    conn: Any, user_id: str, *, title: str = "", focus_person_id: int | None = None
) -> dict[str, Any]:
    with conn.cursor(row_factory=dict_row) as cur:
        cur.execute(
            f"INSERT INTO conversation (user_id, title, focus_person_id) "
            f"VALUES (%s, %s, %s) RETURNING {_CONV_COLS}",
            [user_id, title or "", focus_person_id],
        )
        return _conv(cur.fetchone())


def list_conversations(conn: Any, user_id: str) -> list[dict[str, Any]]:
    with conn.cursor(row_factory=dict_row) as cur:
        cur.execute(
            "SELECT c.id, c.title, c.focus_person_id, c.created_at, c.updated_at, "
            "COUNT(m.id) AS message_count "
            "FROM conversation c LEFT JOIN conv_message m ON m.conversation_id = c.id "
            "WHERE c.user_id = %s "
            "GROUP BY c.id ORDER BY c.updated_at DESC, c.id DESC",
            [user_id],
        )
        return [_conv(r) for r in cur.fetchall()]


def get_conversation(conn: Any, user_id: str, conv_id: int) -> dict[str, Any] | None:
    with conn.cursor(row_factory=dict_row) as cur:
        cur.execute(
            f"SELECT {_CONV_COLS} FROM conversation WHERE id = %s AND user_id = %s",
            [conv_id, user_id],
        )
        row = cur.fetchone()
    return _conv(row) if row else None


def rename_conversation(
    conn: Any, user_id: str, conv_id: int, title: str
) -> dict[str, Any] | None:
    with conn.cursor(row_factory=dict_row) as cur:
        cur.execute(
            f"UPDATE conversation SET title = %s, updated_at = now() "
            f"WHERE id = %s AND user_id = %s RETURNING {_CONV_COLS}",
            [title.strip(), conv_id, user_id],
        )
        row = cur.fetchone()
    return _conv(row) if row else None


def delete_conversation(conn: Any, user_id: str, conv_id: int) -> bool:
    with conn.cursor() as cur:
        cur.execute(
            "DELETE FROM conversation WHERE id = %s AND user_id = %s", [conv_id, user_id]
        )
        return bool(cur.rowcount and cur.rowcount > 0)


def list_messages(conn: Any, user_id: str, conv_id: int) -> list[dict[str, Any]]:
    with conn.cursor(row_factory=dict_row) as cur:
        cur.execute(
            "SELECT id, role, content, tools_json, created_at FROM conv_message "
            "WHERE conversation_id = %s AND user_id = %s ORDER BY id",
            [conv_id, user_id],
        )
        return [
            {
                "id": int(r["id"]),
                "role": r["role"],
                "content": r["content"],
                "tools": r["tools_json"] or [],
                "created_at": r["created_at"],
            }
            for r in cur.fetchall()
        ]


def add_message(
    conn: Any,
    user_id: str,
    conv_id: int,
    *,
    role: str,
    content: str,
    tools: list[dict[str, Any]] | None = None,
) -> int:
    with conn.cursor() as cur:
        cur.execute(
            "INSERT INTO conv_message (conversation_id, user_id, role, content, tools_json) "
            "VALUES (%s, %s, %s, %s, %s) RETURNING id",
            [conv_id, user_id, role, content, Json(tools or [])],
        )
        return int(cur.fetchone()[0])


def clear_focus(conn: Any, user_id: str, person_id: int) -> None:
    """把所有以 person_id 为焦点的线程焦点置空 —— 删联系人时清掉悬空引用, 不留僵尸。"""
    with conn.cursor() as cur:
        cur.execute(
            "UPDATE conversation SET focus_person_id = NULL "
            "WHERE focus_person_id = %s AND user_id = %s",
            [person_id, user_id],
        )


def touch_conversation(
    conn: Any,
    user_id: str,
    conv_id: int,
    *,
    fallback_title: str | None = None,
    focus_person_id: int | None = None,
) -> None:
    """bump updated_at; 标题仍空则用 fallback_title(首句)补上; 顺带记住焦点联系人。"""
    with conn.cursor() as cur:
        cur.execute(
            "UPDATE conversation SET updated_at = now(), "
            "title = CASE WHEN title = '' AND %s <> '' THEN %s ELSE title END, "
            "focus_person_id = COALESCE(%s, focus_person_id) "
            "WHERE id = %s AND user_id = %s",
            [
                fallback_title or "",
                fallback_title or "",
                focus_person_id,
                conv_id,
                user_id,
            ],
        )
