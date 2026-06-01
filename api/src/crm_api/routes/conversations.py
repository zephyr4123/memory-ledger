"""/api/conversations —— 对话线程的完整 CRUD + 取某线程的消息记录。

对话 = 跨对话记忆的载体: 不同线程查到的是同一份按 user_id 共享的真相。线程本身只存
聊天容器与消息, 不持有记忆。
"""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends, HTTPException

from .. import conversations as store
from ..config import Settings
from ..deps import get_conn, get_settings
from ..schemas import (
    ConversationOut,
    ConvMessageOut,
    CreateConversationRequest,
    RenameConversationRequest,
)

router = APIRouter()


@router.get("/conversations", response_model=list[ConversationOut])
def list_conversations(
    conn: Any = Depends(get_conn),
    settings: Settings = Depends(get_settings),
) -> list[dict[str, Any]]:
    return store.list_conversations(conn, settings.user_id)


@router.post("/conversations", response_model=ConversationOut)
def create_conversation(
    body: CreateConversationRequest,
    conn: Any = Depends(get_conn),
    settings: Settings = Depends(get_settings),
) -> dict[str, Any]:
    return store.create_conversation(
        conn, settings.user_id, title=body.title, focus_person_id=body.focus_person_id
    )


@router.patch("/conversations/{conv_id}", response_model=ConversationOut)
def rename_conversation(
    conv_id: int,
    body: RenameConversationRequest,
    conn: Any = Depends(get_conn),
    settings: Settings = Depends(get_settings),
) -> dict[str, Any]:
    row = store.rename_conversation(conn, settings.user_id, conv_id, body.title)
    if row is None:
        raise HTTPException(status_code=404, detail="conversation not found")
    return row


@router.delete("/conversations/{conv_id}")
def delete_conversation(
    conv_id: int,
    conn: Any = Depends(get_conn),
    settings: Settings = Depends(get_settings),
) -> dict[str, bool]:
    ok = store.delete_conversation(conn, settings.user_id, conv_id)
    if not ok:
        raise HTTPException(status_code=404, detail="conversation not found")
    return {"ok": True}


@router.get("/conversations/{conv_id}/messages", response_model=list[ConvMessageOut])
def list_messages(
    conv_id: int,
    conn: Any = Depends(get_conn),
    settings: Settings = Depends(get_settings),
) -> list[dict[str, Any]]:
    if store.get_conversation(conn, settings.user_id, conv_id) is None:
        raise HTTPException(status_code=404, detail="conversation not found")
    return store.list_messages(conn, settings.user_id, conv_id)
