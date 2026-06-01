"""集成: crm_api 路由闭环 (testcontainers PG + FakeResponder, 不打真网络)。

覆盖: health(mock) / 联系人列表 / seed 后真相 / 账本流水(含 supersede+reject) /
对话一轮(SSE)→ banner / confirm → 真相变 / as-of 时光机。
"""

from __future__ import annotations

import json
from collections.abc import Iterator
from typing import Any

import psycopg
import pytest
from fastapi.testclient import TestClient
from memory_ledger import ProposedIntent, Response
from testcontainers.postgres import PostgresContainer

from crm_api.config import Settings
from crm_api.db import ensure_schema
from crm_api.deps import get_responder
from crm_api.main import create_app


class FakeResponder:
    """确定性 responder: 回一句话 + 提一条 PATCH employer→Stripe。"""

    reply = "Sure — I'll propose updating her employer to Stripe for your confirmation."

    def respond(self, *, utterance: str, snapshot: str, turn: int) -> Response:
        return Response(self.reply, (self._patch(utterance, 1),))

    def stream_turn(
        self, *, utterance: str, ctx: Any, history: Any = None
    ) -> Iterator[tuple[str, Any]]:
        # 先"查一把"(可视化用), 再回复, 再暂存一条 PATCH
        yield ("tool_call", {"id": "c0", "name": "get_contact",
                             "args": {"contact_id": ctx.focus_person_id}})
        yield ("tool_result", {"id": "c0", "name": "get_contact", "ok": True})
        yield ("delta", self.reply)
        yield ("intents", [self._patch(utterance, ctx.focus_person_id)])

    @staticmethod
    def _patch(utterance: str, person_id: int) -> ProposedIntent:
        return ProposedIntent(
            kind="PATCH", target_entity="person", patch_json={"employer": "Stripe"},
            target_row_id=str(person_id), target_field="employer",
            source_quote=utterance, confidence=0.9,
        )


@pytest.fixture(scope="module")
def pg_url() -> Iterator[str]:
    with PostgresContainer("postgres:16-alpine") as pg:
        yield pg.get_connection_url().replace("postgresql+psycopg2", "postgresql")


@pytest.fixture()
def client(pg_url: str) -> Iterator[TestClient]:
    # 每个测试重置库 → lifespan 重新 seed 出干净一致的 Sarah/Marcus (id 从 1)
    with psycopg.connect(pg_url, autocommit=True) as conn:
        ensure_schema(conn)
        with conn.cursor() as cur:
            cur.execute("TRUNCATE l15_change_intents, person, todo_item, project "
                        "RESTART IDENTITY CASCADE")
    settings = Settings(
        database_url=pg_url, llm_model="fake", llm_api_key=None, llm_base_url=None,
        user_id="u1", cors_origins=(),
    )
    app = create_app(settings)
    app.dependency_overrides[get_responder] = FakeResponder
    with TestClient(app) as c:
        yield c


def _sse_event(text: str, event: str) -> dict[str, Any]:
    """从 SSE 文本里取某 event 的 data JSON。"""
    for block in text.split("\n\n"):
        if f"event: {event}" in block:
            for line in block.splitlines():
                if line.startswith("data:"):
                    return json.loads(line[len("data:"):].strip())
    raise AssertionError(f"event {event!r} not found in stream")


def test_health_reports_mock_without_key(client: TestClient) -> None:
    r = client.get("/api/health")
    assert r.status_code == 200
    assert r.json()["llm"] == "mock"


def test_people_list_and_seeded_truth(client: TestClient) -> None:
    people = client.get("/api/people").json()
    names = {p["full_name"] for p in people}
    assert {"林思颖", "赵明轩"} <= names
    sarah = client.get("/api/people/1").json()
    assert sarah["employer"] == "Globex"  # 晨星科技 → 蓝湖科技 → Globex (seed)
    assert sarah["location"] == "上海"  # 柏林 被拒


def test_ledger_history_shows_supersede_and_reject(client: TestClient) -> None:
    events = client.get("/api/people/1/ledger").json()
    statuses = {e["status"] for e in events}
    assert "SUPERSEDED" in statuses  # 旧 employer 被链式取代
    assert "REJECTED" in statuses  # Berlin 改动被拒
    # 逐字溯源在
    assert any(e.get("source_quote") for e in events)


def test_turn_proposes_patch_then_confirm_changes_truth(client: TestClient) -> None:
    conv = client.post("/api/conversations", json={"focus_person_id": 1}).json()
    cid = conv["id"]
    r = client.post(
        "/api/turns",
        json={"utterance": "she's at Stripe now", "conversation_id": cid, "person_id": 1},
    )
    assert r.status_code == 200
    done = _sse_event(r.text, "done")
    assert len(done["banners"]) == 1  # 高危 PATCH → 待确认, 不偷偷改
    banner = done["banners"][0]
    assert banner["target_field"] == "employer" and banner["proposed_value"] == "Stripe"
    # 工具调用作为事件被流式吐出 (前端据此可视化)
    assert _sse_event(r.text, "tool_call")["name"] == "get_contact"
    # 确认前: 真相仍是 Globex
    assert client.get("/api/people/1").json()["employer"] == "Globex"
    # 确认后: 真相变 Stripe
    assert client.post("/api/intents/confirm",
                       json={"intent_ids": [banner["intent_id"]]}).json()["affected"] == 1
    assert client.get("/api/people/1").json()["employer"] == "Stripe"
    # 两条消息已落盘, agent 那条带工具调用回执; 线程自动起了标题
    msgs = client.get(f"/api/conversations/{cid}/messages").json()
    assert [m["role"] for m in msgs] == ["user", "agent"]
    assert msgs[1]["tools"][0]["name"] == "get_contact"
    assert client.get("/api/conversations").json()[0]["title"] != ""


def test_create_person(client: TestClient) -> None:
    p = client.post(
        "/api/people",
        json={"full_name": "周深", "employer": "声入人心", "comm_pref": "短信"},
    ).json()
    assert p["full_name"] == "周深" and p["employer"] == "声入人心"
    assert p["comm_pref"] == "sms"  # 中文 → canonical enum
    assert any(x["full_name"] == "周深" for x in client.get("/api/people").json())
    # full_name 必填
    assert client.post("/api/people", json={"employer": "X"}).status_code == 422


def test_update_person_overrides_agent_value(client: TestClient) -> None:
    # 1 号现在 employer=Globex(agent 改的); 用户直接编辑成"网易" → USER_DIRECT 应压过
    out = client.patch("/api/people/1", json={"employer": "网易"}).json()
    assert out["employer"] == "网易"
    assert client.get("/api/people/1").json()["employer"] == "网易"
    # 留痕: 账本里出现一条 USER_DIRECT 的 employer PATCH
    events = client.get("/api/people/1/ledger").json()
    assert any(
        e["source_layer"] == "USER_DIRECT" and e["target_field"] == "employer"
        and e["status"] == "APPLIED"
        for e in events
    )


def test_delete_person_cascades(client: TestClient) -> None:
    # 建个聚焦 1 号的线程, 用来验证删人后焦点被置空(线程保留)
    conv = client.post("/api/conversations", json={"focus_person_id": 1}).json()
    before = client.get("/api/people/1/ledger").json()
    assert len(before) > 0
    res = client.delete("/api/people/1").json()
    assert res["ok"] is True and res["purged_intents"] >= len(before)
    # 真相 404 + 列表里消失
    assert client.get("/api/people/1").status_code == 404
    assert all(x["id"] != 1 for x in client.get("/api/people").json())
    # 关联线程焦点被置空(不留悬空引用), 线程本身保留
    convs = {c["id"]: c for c in client.get("/api/conversations").json()}
    assert conv["id"] in convs and convs[conv["id"]]["focus_person_id"] is None
    # 删不存在 → 404
    assert client.delete("/api/people/1").status_code == 404


def test_conversation_crud(client: TestClient) -> None:
    c = client.post("/api/conversations", json={"focus_person_id": 1}).json()
    cid = c["id"]
    assert c["title"] == "" and c["focus_person_id"] == 1
    assert any(x["id"] == cid for x in client.get("/api/conversations").json())
    renamed = client.patch(f"/api/conversations/{cid}", json={"title": "工作近况"}).json()
    assert renamed["title"] == "工作近况"
    assert client.delete(f"/api/conversations/{cid}").json()["ok"] is True
    assert all(x["id"] != cid for x in client.get("/api/conversations").json())
    assert client.delete(f"/api/conversations/{cid}").status_code == 404


def test_as_of_time_travel(client: TestClient) -> None:
    # seed 之前的时点: 没有任何 PATCH 生效 → 回退到 raw 种子值 晨星科技
    past = client.get("/api/people/1", params={"as_of": "2000-01-01T00:00:00Z"}).json()
    assert past["employer"] == "晨星科技"
    # 现在: Globex
    assert client.get("/api/people/1").json()["employer"] == "Globex"
