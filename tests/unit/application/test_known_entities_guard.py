"""单元: MemoryLedger.known_entities fail-early 闸门 (无需 DB).

证明: 配了 known_entities 时, 未知实体在任何 repo 调用前就被丢弃 (返回 None);
默认 None 时行为完全不变 (放行, 交给 DB CHECK/FK 兜底).
"""

from __future__ import annotations

from memory_ledger import MemoryLedger
from memory_ledger.domain.intents import IntentRecord
from memory_ledger.ports.repository import InsertOutcome


class RecordingRepo:
    def __init__(self) -> None:
        self.insert_calls = 0

    def insert(self, record: IntentRecord, *, auto_apply: bool) -> InsertOutcome:
        self.insert_calls += 1
        return InsertOutcome(1, created=True)

    def confirm(self, user_id, intent_ids):  # pragma: no cover
        return 0

    def reject(self, user_id, intent_ids, reason=""):  # pragma: no cover
        return 0

    def expire_before(self, cutoff, *, user_id=None, target_entity=None):  # pragma: no cover
        return []

    def effective(self, entity, user_id, row_id, *, as_of=None):  # pragma: no cover
        return None


def _insert(led: MemoryLedger, entity: str) -> int | None:
    return led.insert_intent(
        user_id="u1", kind="ASSERT", target_entity=entity, target_row_id="1",
        patch_json={"a": 1}, source_layer="L2_CHAT",
        source_table="t", source_id="m1", confidence=0.9,
    )


def test_unknown_entity_rejected_before_repo_call():
    repo = RecordingRepo()
    led = MemoryLedger(repo, known_entities={"todo_item", "project"})
    result = _insert(led, "person")  # 未在白名单
    assert result is None
    assert repo.insert_calls == 0  # 根本没碰 repo


def test_known_entity_passes_through():
    repo = RecordingRepo()
    led = MemoryLedger(repo, known_entities={"todo_item", "person"})
    result = _insert(led, "person")
    assert result == 1
    assert repo.insert_calls == 1


def test_none_default_preserves_behavior():
    # 不配 known_entities → 不预检, 任何实体都放行到 repo (DB 才是兜底)
    repo = RecordingRepo()
    led = MemoryLedger(repo)  # known_entities 默认 None
    result = _insert(led, "anything_goes")
    assert result == 1
    assert repo.insert_calls == 1
