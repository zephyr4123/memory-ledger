"""单元: domain.conversation 类型契约 (frozen / 默认值 / 不可变). 无需 DB."""

from __future__ import annotations

import dataclasses

import pytest

from memory_ledger.domain.conversation import ProposedIntent, Response


def test_proposed_intent_is_frozen():
    pi = ProposedIntent(kind="PATCH", target_entity="person", patch_json={"employer": "Acme"})
    with pytest.raises(dataclasses.FrozenInstanceError):
        pi.confidence = 0.5  # type: ignore[misc]


def test_proposed_intent_defaults():
    pi = ProposedIntent(kind="ASSERT", target_entity="person", patch_json={"a": 1})
    assert pi.target_row_id is None
    assert pi.target_field is None
    assert pi.source_quote is None
    assert pi.confidence == 1.0
    assert pi.reason == ""


def test_response_is_frozen_and_defaults_empty_intents():
    resp = Response(reply="ok")
    assert resp.intents == ()
    with pytest.raises(dataclasses.FrozenInstanceError):
        resp.reply = "changed"  # type: ignore[misc]


def test_response_holds_intent_tuple():
    intents = (
        ProposedIntent(kind="PATCH", target_entity="person",
                       target_field="employer", patch_json={"employer": "Acme"}),
        ProposedIntent(kind="ASSERT", target_entity="person",
                       patch_json={"note": "x"}, source_quote="she joined Acme"),
    )
    resp = Response(reply="done", intents=intents)
    assert len(resp.intents) == 2
    assert resp.intents[0].kind == "PATCH"
    assert resp.intents[1].source_quote == "she joined Acme"
