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

    def stream_turn(self, *, utterance: str, ctx: Any) -> Iterator[tuple[str, Any]]:
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
    r = client.post("/api/turns", json={"utterance": "she's at Stripe now", "person_id": 1})
    assert r.status_code == 200
    done = _sse_event(r.text, "done")
    assert len(done["banners"]) == 1  # 高危 PATCH → 待确认, 不偷偷改
    banner = done["banners"][0]
    assert banner["target_field"] == "employer" and banner["proposed_value"] == "Stripe"
    # 确认前: 真相仍是 Globex
    assert client.get("/api/people/1").json()["employer"] == "Globex"
    # 确认后: 真相变 Stripe
    assert client.post("/api/intents/confirm",
                       json={"intent_ids": [banner["intent_id"]]}).json()["affected"] == 1
    assert client.get("/api/people/1").json()["employer"] == "Stripe"


def test_as_of_time_travel(client: TestClient) -> None:
    # seed 之前的时点: 没有任何 PATCH 生效 → 回退到 raw 种子值 晨星科技
    past = client.get("/api/people/1", params={"as_of": "2000-01-01T00:00:00Z"}).json()
    assert past["employer"] == "晨星科技"
    # 现在: Globex
    assert client.get("/api/people/1").json()["employer"] == "Globex"
