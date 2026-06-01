"""/api/turns —— 对话式产品核心 (SSE 流式, agent loop, 落对话线程)。

一轮:
  1. 校验对话线程归属 → 借一条 DB 连接, 装配 per-request 账本 + ToolContext(焦点联系人)。
  2. 落用户这句话 → 取该线程的历史(同线程内真多轮)→ 流式跑 agent loop:
     小本自主调读工具查信息(边查边把"调了哪把工具"作为事件吐给前端可视化), 边吐回复 token,
     边把要记的改动暂存。信息不再 prefill, 由它自己决定查什么。
  3. loop 结束: 落 agent 这条回复(含工具调用回执)→ 写暂存 intent(低危直落 / 高危 PATCH →
     PROPOSED 出 banner)→ 顺手把线程标题(首句)、updated_at、焦点联系人记下。
  4. SSE done: banner + 刷新后的真相 + 账本流水。
任何异常都保证至少发一次 done(否则前端会永久卡在"输入中")。
"""

from __future__ import annotations

import json
import uuid
from collections.abc import Iterator
from typing import Any

from fastapi import APIRouter, Depends, Request
from fastapi.responses import StreamingResponse

from .. import conversations as store
from ..config import Settings
from ..db import ledger_for
from ..deps import get_responder, get_settings
from ..responder import TurnResponder
from ..schemas import BannerOut, LedgerEventOut, PersonOut, TurnRequest
from ..tools import ToolContext

router = APIRouter()

_TITLE_MAX = 18
_ERR_MSG = "小本暂时遇到了点状况，刚才那句未能记录，请稍后重试。"


def _sse(event: str, data: dict[str, Any]) -> str:
    body = json.dumps(data, ensure_ascii=False, default=str)
    return f"event: {event}\ndata: {body}\n\n"


def _refresh(ledger: Any, user_id: str, person_id: int | None) -> tuple[Any, list[Any]]:
    if person_id is None:
        return None, []
    eff = ledger.effective("person", user_id, person_id)
    person = PersonOut.from_effective(eff) if eff is not None else None
    events = [LedgerEventOut.from_row(r) for r in ledger.history("person", user_id, person_id)]
    return person, events


def _first_person_id(conn: Any, user_id: str) -> int | None:
    with conn.cursor() as cur:
        cur.execute(
            "SELECT id FROM person WHERE user_id = %s AND deleted = false ORDER BY id LIMIT 1",
            [user_id],
        )
        row = cur.fetchone()
    return int(row[0]) if row else None


def _title_from(utterance: str) -> str:
    one_line = " ".join(utterance.split())
    return one_line[:_TITLE_MAX]


@router.post("/turns")
def run_turn(
    body: TurnRequest,
    request: Request,
    settings: Settings = Depends(get_settings),
    responder: TurnResponder = Depends(get_responder),
) -> StreamingResponse:
    pool = request.app.state.pool
    user_id = settings.user_id
    conv_id = body.conversation_id

    def gen() -> Iterator[str]:
        sent_done = False
        person_id: int | None = None
        try:
            # 整轮持一条连接: agent 的读工具在 loop 中途要查库
            with pool.connection() as conn:
                conv = store.get_conversation(conn, user_id, conv_id)
                if conv is None:
                    yield _sse(
                        "done",
                        {"banners": [], "person": None, "ledger": [],
                         "error": "这个对话不存在或不属于你。"},
                    )
                    return

                # 焦点联系人: 显式传的优先, 否则用线程记住的, 再否则第一个联系人
                person_id = (
                    body.person_id
                    or conv.get("focus_person_id")
                    or _first_person_id(conn, user_id)
                )
                ledger = ledger_for(conn)
                ctx = ToolContext(
                    conn=conn, ledger=ledger, user_id=user_id,
                    focus_person_id=person_id if person_id is not None else 0,
                )

                # 先落用户这句(即使后面出错也留痕)+ 取同线程历史喂给 agent
                store.add_message(conn, user_id, conv_id, role="user", content=body.utterance)
                history = store.list_messages(conn, user_id, conv_id)

                reply_parts: list[str] = []
                tool_log: dict[str, dict[str, Any]] = {}  # id → {name, args, ok, status}
                intents: list[Any] = []
                for kind, payload in responder.stream_turn(
                    utterance=body.utterance, ctx=ctx, history=history
                ):
                    if kind == "delta":
                        reply_parts.append(payload)
                        yield _sse("reply_delta", {"text": payload})
                    elif kind == "tool_call":
                        tool_log[payload["id"]] = {
                            "id": payload["id"], "name": payload["name"],
                            "args": payload.get("args") or {}, "status": "running",
                        }
                        yield _sse("tool_call", payload)
                    elif kind == "tool_result":
                        rec = tool_log.get(payload["id"])
                        if rec is not None:
                            rec["ok"] = bool(payload.get("ok"))
                            rec["status"] = "done" if payload.get("ok") else "error"
                        yield _sse("tool_result", payload)
                    elif kind == "intents":
                        intents = list(payload)

                # 落 agent 这条回复(正文 + 工具调用回执, 供回看)
                reply_text = "".join(reply_parts)
                store.add_message(
                    conn, user_id, conv_id, role="agent",
                    content=reply_text, tools=list(tool_log.values()),
                )

                # 落盘暂存的 intent (PATCH 高危→PROPOSED 出 banner; 其余低危直落)
                source_id = f"conv{conv_id}-turn-{uuid.uuid4().hex[:8]}"
                banners: list[BannerOut] = []
                for pi in intents:
                    layer = "AGENT_INFERENCE" if pi.kind == "PATCH" else "L2_CHAT"
                    res = ledger.write_intent(
                        user_id=user_id, kind=pi.kind, target_entity="person",
                        patch_json=pi.patch_json, source_layer=layer,
                        source_table="chat_message", source_id=source_id,
                        target_row_id=pi.target_row_id or str(person_id),
                        target_field=pi.target_field, source_quote=pi.source_quote,
                        confidence=pi.confidence,
                    )
                    if res.needs_confirmation:
                        banners.append(
                            BannerOut(
                                intent_id=res.intent_id, target_field=res.target_field,
                                proposed_value=res.proposed_value, confidence=pi.confidence,
                            )
                        )

                # 线程收尾: 标题(首句)/updated_at/焦点
                store.touch_conversation(
                    conn, user_id, conv_id,
                    fallback_title=_title_from(body.utterance),
                    focus_person_id=person_id,
                )

                person, events = _refresh(ledger, user_id, person_id)
                yield _sse(
                    "done",
                    {
                        "banners": [b.model_dump() for b in banners],
                        "person": person.model_dump() if person is not None else None,
                        "ledger": [e.model_dump() for e in events],
                    },
                )
                sent_done = True
        except Exception:  # noqa: BLE001 — 任何失败都要给前端一个终态, 否则永久转圈
            if not sent_done:
                person_d, ledger_d = None, []
                try:  # 尽力保留时间轴(别用空数组把它冲掉)
                    with pool.connection() as c2:
                        p, ev = _refresh(ledger_for(c2), user_id, person_id)
                        person_d = p.model_dump() if p is not None else None
                        ledger_d = [e.model_dump() for e in ev]
                        store.add_message(
                            c2, user_id, conv_id, role="agent", content=_ERR_MSG,
                        )
                except Exception:  # noqa: BLE001
                    pass
                yield _sse(
                    "done",
                    {
                        "banners": [],
                        "person": person_d,
                        "ledger": ledger_d,
                        "error": _ERR_MSG,
                    },
                )

    return StreamingResponse(
        gen(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )
