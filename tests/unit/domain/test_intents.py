"""单元: domain.intents — normalize / validate (无需 DB)."""

from __future__ import annotations

import pytest

from memory_ledger import IntentShapeError, normalize_intent, validate_intent_shape


def test_field_alias_renames_target_and_patch_key():
    out = normalize_intent(
        {"kind": "PATCH", "target_field": "deadline", "patch_json": {"deadline": "2026-05-30"}},
        field_aliases={"deadline": "due_date"},
    )
    assert out["target_field"] == "due_date"
    assert out["patch_json"] == {"due_date": "2026-05-30"}


def test_value_alias_maps_enum():
    out = normalize_intent(
        {"kind": "PATCH", "target_field": "status", "patch_json": {"status": "done"}},
        value_aliases={"status": {"done": "completed"}},
    )
    assert out["patch_json"]["status"] == "completed"


def test_normalize_does_not_mutate_input():
    src = {"kind": "PATCH", "target_field": "deadline", "patch_json": {"deadline": "x"}}
    normalize_intent(src, field_aliases={"deadline": "due_date"})
    assert src["target_field"] == "deadline"  # 原 dict 不变


@pytest.mark.parametrize(
    "intent",
    [
        {"kind": "PATCH", "target_field": "due_date", "patch_json": {"due_date": "x"}},
        {"kind": "ASSERT", "patch_json": {"recipient": "mom"}},
        {"kind": "ANNOTATE", "patch_json": {"annotation": "note"}},
        {"kind": "FLAG", "target_field": "due_date", "patch_json": {"flag_reason": "stale"}},
    ],
)
def test_valid_shapes_pass(intent):
    validate_intent_shape(intent)  # 不抛即通过


@pytest.mark.parametrize(
    "intent",
    [
        {"kind": "PATCH", "patch_json": {"due_date": "x"}},  # 缺 target_field
        {"kind": "PATCH", "target_field": "due_date", "patch_json": {"other": 1}},  # key 不匹配
        {"kind": "ASSERT", "patch_json": {}},  # 空
        {"kind": "ANNOTATE", "patch_json": {"annotation": 123}},  # 非字符串
        {"kind": "FLAG", "target_field": "x", "patch_json": {"nope": 1}},  # 缺 flag_reason
        {"kind": "WHAT", "patch_json": {"a": 1}},  # 未知 kind
    ],
)
def test_invalid_shapes_raise(intent):
    with pytest.raises(IntentShapeError):
        validate_intent_shape(intent)
