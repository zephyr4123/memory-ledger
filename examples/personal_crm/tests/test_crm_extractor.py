"""单元 (示例, 无 I/O): MockExtractor 的纯度/确定性 + 脚本契约."""

from __future__ import annotations

import pytest

from examples.personal_crm.mock_extractor import MockExtractor
from examples.personal_crm.transcript import TRANSCRIPT


def test_extract_returns_scripted_extraction_per_turn():
    ex = MockExtractor(TRANSCRIPT)
    for turn, st in enumerate(TRANSCRIPT):
        out = ex.extract(utterance=st.utterance, snapshot="ignored", turn=turn)
        assert out is st.extraction


def test_extract_ignores_snapshot_pure_function():
    ex = MockExtractor(TRANSCRIPT)
    a = ex.extract(utterance=TRANSCRIPT[0].utterance, snapshot="X", turn=0)
    b = ex.extract(utterance=TRANSCRIPT[0].utterance, snapshot="totally different", turn=0)
    assert a is b  # snapshot 不影响输出


def test_transcript_drift_raises():
    ex = MockExtractor(TRANSCRIPT)
    with pytest.raises(AssertionError):
        ex.extract(utterance="wrong line", snapshot="", turn=0)


def test_all_source_quotes_are_verbatim_substrings():
    # §9 原话规则: 每条非空 source_quote 必须是当轮 utterance 的逐字子串
    for st in TRANSCRIPT:
        for pi in st.extraction.intents:
            if pi.source_quote:
                assert pi.source_quote in st.utterance, (
                    f"turn {st.source_id}: quote {pi.source_quote!r} "
                    f"not a substring of {st.utterance!r}"
                )


def test_source_ids_unique():
    ids = [st.source_id for st in TRANSCRIPT]
    assert len(ids) == len(set(ids))  # 幂等 + 溯源键唯一
