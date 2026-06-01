"""/api/turns —— 对话式产品核心 (SSE 流式, agent loop)。

一轮:
  1. 借一条 DB 连接, 装配 per-request 账本 + ToolContext(焦点联系人)。
  2. 流式跑 agent loop: 小本自主调读工具(查联系人/全貌/历史/待办)→ 边吐回复 token,
     边把要记的改动暂存(写工具)。信息不再 prefill, 由它自己决定查什么。
  3. loop 结束后写暂存 intent(低危直落 / 高危 PATCH → PROPOSED 出 banner)。
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

from ..config import Settings
from ..db import ledger_for
from ..deps import get_responder, get_settings
from ..responder import TurnResponder
from ..schemas import BannerOut, LedgerEventOut, PersonOut, TurnRequest
from ..tools import ToolContext

router = APIRouter()


def _sse(event: str, data: dict[str, Any]) -> str:
    body = json.dumps(data, ensure_ascii=False, default=str)
    return f"event: {event}\ndata: {body}\n\n"


def _refresh(ledger: Any, user_id: str, person_id: int) -> tuple[Any, list[Any]]:
    eff = ledger.effective("person", user_id, person_id)
    person = PersonOut.from_effective(eff) if eff is not None else None
    events = [LedgerEventOut.from_row(r) for r in ledger.history("person", user_id, person_id)]
    return person, events


@router.post("/turns")
def run_turn(
    body: TurnRequest,
    request: Request,
    settings: Settings = Depends(get_settings),
    responder: TurnResponder = Depends(get_responder),
) -> StreamingResponse:
    pool = request.app.state.pool
    user_id = settings.user_id
    person_id = body.person_id

    def gen() -> Iterator[str]:
        sent_done = False
        try:
            # 整轮持一条连接: agent 的读工具在 loop 中途要查库
            with pool.connection() as conn:
                ledger = ledger_for(conn)
                ctx = ToolContext(
                    conn=conn, ledger=ledger, user_id=user_id, focus_person_id=person_id
                )

                intents: list[Any] = []
                for kind, payload in responder.stream_turn(utterance=body.utterance, ctx=ctx):
                    if kind == "delta":
                        yield _sse("reply_delta", {"text": payload})
                    elif kind == "intents":
                        intents = list(payload)

                # 落盘暂存的 intent (PATCH 高危→PROPOSED 出 banner; 其余低危直落)
                source_id = f"turn-{uuid.uuid4().hex[:12]}"
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
                except Exception:  # noqa: BLE001
                    pass
                yield _sse(
                    "done",
                    {
                        "banners": [],
                        "person": person_d,
                        "ledger": ledger_d,
                        "error": "小本这会儿出错了，刚才那句没记上，稍后再试一次～",
                    },
                )

    return StreamingResponse(
        gen(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )
