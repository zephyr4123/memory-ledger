"""单元: application.caching.SnapshotCache — 细粒度失效 (无需 DB)."""

from __future__ import annotations

from memory_ledger import SnapshotCache


def test_cache_hit_and_fine_grained_invalidate():
    c = SnapshotCache()
    calls = {"n": 0}

    def build() -> str:
        calls["n"] += 1
        return f"snap{calls['n']}"

    assert c.get("u1", "2026-06-01", build) == "snap1"
    assert c.get("u1", "2026-06-01", build) == "snap1"  # hit
    assert calls["n"] == 1
    # 细粒度: 只失效另一个 scope, 当前 scope 仍命中
    c.invalidate("u1", "2026-06-02")
    assert c.get("u1", "2026-06-01", build) == "snap1"
    assert calls["n"] == 1
    # 失效当前 scope → 重建
    c.invalidate("u1", "2026-06-01")
    assert c.get("u1", "2026-06-01", build) == "snap2"
    assert calls["n"] == 2


def test_cache_invalidate_all_scopes_for_user():
    c = SnapshotCache()
    c.get("u1", "a", lambda: "x")
    c.get("u1", "b", lambda: "y")
    c.get("u2", "a", lambda: "z")
    assert c.invalidate("u1") == 2
    assert c.invalidate("u2") == 1


def test_hit_rate():
    c = SnapshotCache()
    c.get("u1", "a", lambda: "x")  # miss
    c.get("u1", "a", lambda: "x")  # hit
    assert c.hit_rate == 0.5
