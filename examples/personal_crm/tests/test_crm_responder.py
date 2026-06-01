"""单元 (示例, 无 I/O): MockResponder 的纯度/确定性 + 脚本契约."""

from __future__ import annotations

import pytest

from examples.personal_crm.responder import MockResponder
from examples.personal_crm.transcript import TRANSCRIPT


def test_respond_returns_scripted_response_per_turn():
    r = MockResponder(TRANSCRIPT)
    for turn, st in enumerate(TRANSCRIPT):
        out = r.respond(utterance=st.utterance, snapshot="ignored", turn=turn)
        assert out is st.response


def test_respond_ignores_snapshot_pure_function():
    r = MockResponder(TRANSCRIPT)
    a = r.respond(utterance=TRANSCRIPT[0].utterance, snapshot="X", turn=0)
    b = r.respond(utterance=TRANSCRIPT[0].utterance, snapshot="totally different", turn=0)
    assert a is b  # snapshot 不影响输出


def test_transcript_drift_raises():
    r = MockResponder(TRANSCRIPT)
    with pytest.raises(AssertionError):
        r.respond(utterance="wrong line", snapshot="", turn=0)


def test_all_source_quotes_are_verbatim_substrings():
    # 原话规则: 每条非空 source_quote 必须是当轮 utterance 的逐字子串
    for st in TRANSCRIPT:
        for pi in st.response.intents:
            if pi.source_quote:
                assert pi.source_quote in st.utterance, (
                    f"turn {st.source_id}: quote {pi.source_quote!r} "
                    f"not a substring of {st.utterance!r}"
                )


def test_source_ids_unique():
    ids = [st.source_id for st in TRANSCRIPT]
    assert len(ids) == len(set(ids))  # 幂等 + 溯源键唯一
