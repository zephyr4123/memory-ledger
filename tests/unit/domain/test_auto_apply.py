"""单元: domain.policies.AutoApplyPolicy — 写风险矩阵 (无需 DB)."""

from __future__ import annotations

from memory_ledger import AutoApplyPolicy


def test_patch_not_auto_applied_by_default():
    pol = AutoApplyPolicy.low_risk_for(["todo_item"])
    assert (
        pol.should_auto_apply(
            {"target_entity": "todo_item", "kind": "PATCH", "confidence": 0.99}
        )
        is False
    )


def test_low_risk_kinds_auto_apply_above_threshold():
    pol = AutoApplyPolicy.low_risk_for(["todo_item"], threshold=0.6)
    for kind in ("ASSERT", "ANNOTATE", "FLAG"):
        assert (
            pol.should_auto_apply(
                {"target_entity": "todo_item", "kind": kind, "confidence": 0.6}
            )
            is True
        )


def test_below_threshold_blocks():
    pol = AutoApplyPolicy.low_risk_for(["todo_item"], threshold=0.6)
    assert (
        pol.should_auto_apply(
            {"target_entity": "todo_item", "kind": "ASSERT", "confidence": 0.5}
        )
        is False
    )


def test_explicit_patch_rule_can_auto_apply():
    pol = AutoApplyPolicy({("calendar_sync", "PATCH"): True})
    assert (
        pol.should_auto_apply(
            {"target_entity": "calendar_sync", "kind": "PATCH", "confidence": 1.0}
        )
        is True
    )
