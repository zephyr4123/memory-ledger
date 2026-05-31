"""Snapshot 读模型缓存 —— application 层 (CQRS 读侧投影缓存).

in-memory、invalidate-on-write、细粒度. 按 ``(user_id, scope)`` 失效, scope
一般是 ref_date.isoformat(), 也允许业务用 entity/row 作更细的 key. 纯
deterministic-rebuild、不持久化 —— 重启不丢业务 (effective view 永远能重建).
"""

from __future__ import annotations

from collections.abc import Callable, Hashable


class SnapshotCache:
    """key = (user_id, scope). scope 一般是 ref_date.isoformat()."""

    def __init__(self) -> None:
        self._store: dict[tuple[str, Hashable], str] = {}
        self.hits = 0
        self.misses = 0

    def get(
        self,
        user_id: str,
        scope: Hashable,
        build_fn: Callable[[], str],
        *,
        force_refresh: bool = False,
    ) -> str:
        """取 snapshot; miss 时调 build_fn (必须是纯函数, 只读 effective view)."""
        key = (user_id, scope)
        if not force_refresh and key in self._store:
            self.hits += 1
            return self._store[key]
        self.misses += 1
        value = build_fn()
        self._store[key] = value
        return value

    def invalidate(self, user_id: str, scope: Hashable | None = None) -> int:
        """失效缓存. scope=None 时失效该 user 全部; 否则只失效该 (user, scope). 返回条数."""
        if scope is not None:
            return 1 if self._store.pop((user_id, scope), None) is not None else 0
        stale = [k for k in self._store if k[0] == user_id]
        for k in stale:
            self._store.pop(k, None)
        return len(stale)

    def clear(self) -> None:
        self._store.clear()

    @property
    def hit_rate(self) -> float:
        total = self.hits + self.misses
        return self.hits / total if total else 0.0
