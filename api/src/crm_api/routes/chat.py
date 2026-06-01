"""/api/turns —— 对话式产品核心 (SSE 流式).

一轮:
  1. 取当前记忆 snapshot (短连接, 读完即还, LLM 调用期间不占 DB 连接)。
  2. 流式调真 LLM: 边吐回复 token (SSE reply_delta) 边收集结构化 intent。
  3. 写每条 intent (低危直落 / 高危 PATCH → PROPOSED), 收集待确认 banner。
  4. SSE done: banner + 刷新后的真相 + 账本流水。
前端据此实时打字、弹 amber 确认闸门、重渲人卡与时间轴。
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
from ..snapshot import build_person_snapshot

router = APIRouter()


def _sse(event: str, data: dict[str, Any]) -> str:
    body = json.dumps(data, ensure_ascii=False, default=str)
    return f"event: {event}\ndata: {body}\n\n"


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
        # 1. snapshot (短连接)
        with pool.connection() as conn:
            snapshot = build_person_snapshot(ledger_for(conn), user_id, [person_id])

        # 2. 流式 LLM
        intents: list[Any] = []
        for kind, payload in responder.stream_turn(
            utterance=body.utterance, snapshot=snapshot, person_id=person_id
        ):
            if kind == "delta":
                yield _sse("reply_delta", {"text": payload})
            elif kind == "intents":
                intents = list(payload)

        # 3. 写 intents → 收集 banner (短连接)
        source_id = f"turn-{uuid.uuid4().hex[:12]}"
        banners: list[BannerOut] = []
        with pool.connection() as conn:
            ledger = ledger_for(conn)
            for pi in intents:
                # PATCH 高危 (AGENT_INFERENCE, 待确认); 其余低危 (L2_CHAT, 直落)
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
                            intent_id=res.intent_id,
                            target_field=res.target_field,
                            proposed_value=res.proposed_value,
                            confidence=pi.confidence,
                        )
                    )
            # 4. 刷新后的真相 + 账本
            eff = ledger.effective("person", user_id, person_id)
            person = PersonOut.from_effective(eff) if eff is not None else None
            events = [
                LedgerEventOut.from_row(r)
                for r in ledger.history("person", user_id, person_id)
            ]

        yield _sse(
            "done",
            {
                "banners": [b.model_dump() for b in banners],
                "person": person.model_dump() if person is not None else None,
                "ledger": [e.model_dump() for e in events],
            },
        )

    return StreamingResponse(
        gen(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )
