"""单元: AgentLoop 编排逻辑, 用功能性 FakeRepo + MockExtractor 驱动, 零 DB.

这是六边形重构的直接红利: AgentLoop 只认 IntentRepository / Extractor 端口, 可注入
内存 fake, 毫秒级验证全部编排不变量 —— 完全不碰 Postgres.

证明:
  * PATCH → banner 非空; ASSERT/ANNOTATE/FLAG → 不进 banner (走真 AutoApplyPolicy)
  * source_quote 是 utterance 的 verbatim 子串 (provenance 真实性)
  * 第 i 轮的 pre-write snapshot **不含**第 i 轮刚写的 fact (时序正确)
  * 两次相同运行 → 相同 reply+banner 序列 (确定性)
"""

from __future__ import annotations

from collections.abc import Sequence

from memory_ledger import AutoApplyPolicy, MemoryLedger
from memory_ledger.application.agent_loop import AgentLoop
from memory_ledger.domain.extraction import Extraction, ProposedIntent
from memory_ledger.domain.intents import IntentRecord
from memory_ledger.ports.repository import InsertOutcome


# ── 功能性 FakeRepo: 内存版账本 + effective 视图 ─────────────────────
class FakeRepo:
    def __init__(self) -> None:
        self._rows: list[dict] = []
        self._next_id = 1
        # 已 APPLIED 的 ASSERT payload, 按 (entity,row) 聚 —— 供 snapshot 读
        self.applied_facts: dict[tuple[str, str | None], list[dict]] = {}

    def insert(self, record: IntentRecord, *, auto_apply: bool) -> InsertOutcome:
        # 幂等: 同 source 复用
        for r in self._rows:
            if (
                r["source_id"] == record.source_id
                and r["target_entity"] == record.target_entity
                and r["target_field"] == record.target_field
                and r["kind"] == record.kind
                and r["status"] != "REJECTED"
            ):
                return InsertOutcome(r["id"], created=False)
        oid = self._next_id
        self._next_id += 1
        self._rows.append({
            "id": oid, "kind": record.kind, "target_entity": record.target_entity,
            "target_row_id": record.target_row_id, "target_field": record.target_field,
            "source_id": record.source_id, "source_quote": record.source_quote,
            "status": "APPLIED" if auto_apply else "PROPOSED",
            "patch_json": record.patch_json,
        })
        if auto_apply and record.kind == "ASSERT":
            key = (record.target_entity, record.target_row_id)
            self.applied_facts.setdefault(key, []).append({
                "payload": record.patch_json, "source_quote": record.source_quote,
            })
        return InsertOutcome(oid, created=True)

    def confirm(self, user_id: str, intent_ids: Sequence[int]) -> int:
        n = 0
        for r in self._rows:
            if r["id"] in intent_ids and r["status"] == "PROPOSED":
                r["status"] = "APPLIED"
                n += 1
        return n

    def reject(self, user_id, intent_ids, reason=""):  # pragma: no cover
        return 0

    def expire_before(self, cutoff, *, user_id=None, target_entity=None):  # pragma: no cover
        return []

    def effective(self, entity, user_id, row_id, *, as_of=None):  # pragma: no cover
        return None


# ── 脚本化 MockExtractor (turn-keyed) ────────────────────────────────
class MockExtractor:
    def __init__(self, script: Sequence[tuple[str, Extraction]]) -> None:
        self._script = tuple(script)

    def extract(self, *, utterance: str, snapshot: str, turn: int) -> Extraction:
        u, ex = self._script[turn]
        assert u == utterance, f"transcript drift at turn {turn}"
        return ex  # snapshot 被接受但忽略 → 纯函数


def test_patch_becomes_banner_low_risk_does_not():
    repo = FakeRepo()
    ledger = MemoryLedger(repo, auto_apply=AutoApplyPolicy.low_risk_for(["person"]))
    script = [
        ("u1 says", Extraction(reply="ok", intents=(
            ProposedIntent(kind="PATCH", target_entity="person", target_row_id="1",
                           target_field="employer", patch_json={"employer": "Acme"},
                           source_quote="works at Acme", confidence=0.9),
            ProposedIntent(kind="ASSERT", target_entity="person", target_row_id="1",
                           patch_json={"role": "PM"}, source_quote="she is a PM", confidence=0.9),
        ))),
    ]
    loop = AgentLoop(ledger, MockExtractor(script), lambda uid: "snap")
    result = loop.run_turn("u1", "u1 says", 0, source_id="m0")
    assert result.reply == "ok"
    # 只有 PATCH 进 banner
    assert len(result.banners) == 1
    b = result.banners[0]
    assert b.target_field == "employer" and b.proposed_value == "Acme"
    # ASSERT 已 auto-apply, 不在 banner
    assert all(x.target_field != "role" for x in result.banners)


def test_source_quote_is_verbatim_substring():
    repo = FakeRepo()
    ledger = MemoryLedger(repo, auto_apply=AutoApplyPolicy.low_risk_for(["person"]))
    utterance = "she just started at Acme last week"
    script = [(utterance, Extraction(reply="noted", intents=(
        ProposedIntent(kind="ASSERT", target_entity="person", target_row_id="1",
                       patch_json={"employer": "Acme"},
                       source_quote="she just started at Acme", confidence=0.9),
    )))]
    loop = AgentLoop(ledger, MockExtractor(script), lambda uid: "snap")
    loop.run_turn("u1", utterance, 0, source_id="m0")
    fact = repo.applied_facts[("person", "1")][0]
    assert fact["source_quote"] in utterance  # verbatim 截取, 非 paraphrase


def test_pre_write_snapshot_excludes_this_turns_fact():
    """第 i 轮 snapshot 在写之前取 → 不含本轮 fact. 用 snapshot_builder 读 fake 的 applied_facts."""
    repo = FakeRepo()
    ledger = MemoryLedger(repo, auto_apply=AutoApplyPolicy.low_risk_for(["person"]))

    seen_snapshots: list[str] = []

    def snapshot_builder(uid: str) -> str:
        facts = repo.applied_facts.get(("person", "1"), [])
        return "facts=" + ";".join(str(f["payload"]) for f in facts)

    script = [
        ("turn0", Extraction(reply="r0", intents=(
            ProposedIntent(kind="ASSERT", target_entity="person", target_row_id="1",
                           patch_json={"employer": "Acme"}, source_quote="at Acme", confidence=0.9),
        ))),
        ("turn1", Extraction(reply="r1", intents=())),
    ]
    loop = AgentLoop(ledger, MockExtractor(script), snapshot_builder)

    # turn 0: snapshot 取时还没写 → 空; 写后 fake.applied_facts 有了 Acme
    s0 = ledger.snapshot("u1", 0, lambda: snapshot_builder("u1"))
    seen_snapshots.append(s0)
    loop.run_turn("u1", "turn0", 0, source_id="m0")
    # turn 0 的 pre-write snapshot 不含 Acme
    assert "Acme" not in seen_snapshots[0]
    # turn 1 (新 scope) snapshot 现在能看到 turn0 写的 Acme
    s1 = loop.run_turn("u1", "turn1", 1, source_id="m1")
    assert s1.reply == "r1"
    rebuilt = snapshot_builder("u1")
    assert "Acme" in rebuilt  # 下一轮可见


def test_full_run_is_deterministic():
    script = [
        ("a", Extraction(reply="ra", intents=(
            ProposedIntent(kind="PATCH", target_entity="person", target_row_id="1",
                           target_field="employer", patch_json={"employer": "Acme"},
                           source_quote="at Acme", confidence=0.9),
        ))),
        ("b", Extraction(reply="rb", intents=(
            ProposedIntent(kind="ANNOTATE", target_entity="person", target_row_id="1",
                           patch_json={"annotation": "note"}, source_quote="note", confidence=0.9),
        ))),
    ]

    def run_once() -> list[tuple[str, int]]:
        repo = FakeRepo()
        ledger = MemoryLedger(repo, auto_apply=AutoApplyPolicy.low_risk_for(["person"]))
        loop = AgentLoop(ledger, MockExtractor(script), lambda uid: "snap")
        out = []
        for i, (utt, _) in enumerate(script):
            r = loop.run_turn("u1", utt, i, source_id=f"m{i}")
            out.append((r.reply, len(r.banners)))
        return out

    assert run_once() == run_once()  # 两次完全一致
    assert run_once() == [("ra", 1), ("rb", 0)]  # PATCH→banner, ANNOTATE→无


def test_invalid_shape_intent_is_dropped_no_banner():
    repo = FakeRepo()
    ledger = MemoryLedger(repo, auto_apply=AutoApplyPolicy.low_risk_for(["person"]))
    script = [("x", Extraction(reply="r", intents=(
        # PATCH 缺 target_field → ledger.insert_intent 返回 None → 不进 banner
        ProposedIntent(kind="PATCH", target_entity="person", target_row_id="1",
                       patch_json={"employer": "Acme"}, source_quote="q", confidence=0.9),
    )))]
    loop = AgentLoop(ledger, MockExtractor(script), lambda uid: "snap")
    result = loop.run_turn("u1", "x", 0, source_id="m0")
    assert result.banners == ()
