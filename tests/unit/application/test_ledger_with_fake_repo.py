"""单元: application.MemoryLedger 用 fake repository (无需 DB).

这是新分层的直接红利: 因为 application 只依赖 IntentRepository 端口, 可以注入
一个内存 fake, 在毫秒级验证编排逻辑 (normalize/validate/auto-apply 决策/缓存失效),
完全不碰 Postgres.
"""

from __future__ import annotations

from datetime import datetime

from memory_ledger import AutoApplyPolicy, MemoryLedger
from memory_ledger.domain.intents import IntentRecord
from memory_ledger.ports.repository import InsertOutcome


class FakeRepo:
    """内存版 IntentRepository: 记录调用, 不连库."""

    def __init__(self) -> None:
        self.inserted: list[tuple[IntentRecord, bool]] = []
        self._next_id = 1

    def insert(self, record: IntentRecord, *, auto_apply: bool) -> InsertOutcome:
        self.inserted.append((record, auto_apply))
        oid = self._next_id
        self._next_id += 1
        return InsertOutcome(oid, created=True)

    def confirm(self, user_id, intent_ids):  # pragma: no cover - 未在本文件用
        return len(list(intent_ids))

    def reject(self, user_id, intent_ids, reason=""):  # pragma: no cover
        return len(list(intent_ids))

    def expire_before(self, cutoff, *, user_id=None, target_entity=None):  # pragma: no cover
        return []

    def effective(self, entity, user_id, row_id, *, as_of=None):  # pragma: no cover
        return None


def test_invalid_shape_short_circuits_before_repo():
    repo = FakeRepo()
    led = MemoryLedger(repo)
    # PATCH 缺 target_field → validate 失败 → 不应触达 repo
    result = led.insert_intent(
        user_id="u1", kind="PATCH", target_entity="todo_item",
        patch_json={"due_date": "x"},  # 没给 target_field
        source_layer="L2_CHAT", source_table="t", source_id="m1",
    )
    assert result is None
    assert repo.inserted == []


def test_field_alias_applied_before_persist():
    repo = FakeRepo()
    led = MemoryLedger(repo, field_aliases={"deadline": "due_date"})
    led.insert_intent(
        user_id="u1", kind="PATCH", target_entity="todo_item",
        target_row_id="1", target_field="deadline",
        patch_json={"deadline": "2026-05-30"},
        source_layer="L2_CHAT", source_table="t", source_id="m1",
    )
    rec, _auto = repo.inserted[0]
    assert rec.target_field == "due_date"
    assert rec.patch_json == {"due_date": "2026-05-30"}


def test_auto_apply_decision_passed_to_repo():
    repo = FakeRepo()
    led = MemoryLedger(repo, auto_apply=AutoApplyPolicy.low_risk_for(["todo_item"]))
    # ASSERT 低风险 → auto=True
    led.insert_intent(
        user_id="u1", kind="ASSERT", target_entity="todo_item", target_row_id="1",
        patch_json={"recipient": "mom"},
        source_layer="L2_CHAT", source_table="t", source_id="m1", confidence=0.9,
    )
    # PATCH 高风险 → auto=False
    led.insert_intent(
        user_id="u1", kind="PATCH", target_entity="todo_item",
        target_row_id="1", target_field="due_date", patch_json={"due_date": "x"},
        source_layer="L2_CHAT", source_table="t", source_id="m2", confidence=0.99,
    )
    assert repo.inserted[0][1] is True   # ASSERT auto
    assert repo.inserted[1][1] is False  # PATCH gated


def test_cache_invalidated_only_on_auto_applied_create():
    repo = FakeRepo()
    led = MemoryLedger(repo, auto_apply=AutoApplyPolicy.low_risk_for(["todo_item"]))
    led.snapshot("u1", "today", lambda: "snap")  # 填缓存
    # PATCH 走 PROPOSED (auto=False) → 不应失效缓存
    led.insert_intent(
        user_id="u1", kind="PATCH", target_entity="todo_item",
        target_row_id="1", target_field="due_date", patch_json={"due_date": "x"},
        source_layer="L2_CHAT", source_table="t", source_id="m1",
    )
    assert led.snapshot("u1", "today", lambda: "REBUILT") == "snap"  # 仍命中
    # ASSERT auto-apply → 应失效
    led.insert_intent(
        user_id="u1", kind="ASSERT", target_entity="todo_item", target_row_id="1",
        patch_json={"recipient": "mom"},
        source_layer="L2_CHAT", source_table="t", source_id="m2", confidence=0.9,
    )
    assert led.snapshot("u1", "today", lambda: "REBUILT") == "REBUILT"  # 已失效重建


def test_expire_before_signature_ok():
    # 仅确保 application 调用 repo.expire_before 不炸 (返回 0 因 fake 返回 [])
    repo = FakeRepo()
    led = MemoryLedger(repo)
    assert led.expire_before(datetime(2026, 1, 1)) == 0
