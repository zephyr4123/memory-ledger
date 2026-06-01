"""IntentRepository 端口 —— 面向 domain 的持久化边界.

application 层只认这个抽象, 不认任何具体 SQL / 数据库. 具体实现
(infrastructure/persistence/postgres_repository.py) 把所有 SQL、advisory lock、
auto-supersede 时序等持久化机制封在里面.

把"账本怎么存"收口到这个端口的收益:
  * application 层可用 fake repository 做无 DB 的纯单元测试
  * 新增持久化后端 = 实现一遍这个 Protocol, 不动 application
"""

from __future__ import annotations

from collections.abc import Sequence
from datetime import datetime
from typing import NamedTuple, Protocol, runtime_checkable

from ..domain.intents import IntentRecord
from .database import Row


class InsertOutcome(NamedTuple):
    """insert 的结果: intent id + 是否真正新建 (用于上层决定要不要失效缓存)."""

    intent_id: int
    created: bool


class UnknownEntityError(LookupError):
    """读一个语法合法但未注册 (无 effective_<entity>_at 函数) 的实体.

    把底层驱动的 UndefinedFunction 包装成一个稳定的领域错误, 让调用方能精确捕获
    "实体没注册" 而不是泛泛的 SQL 错误.
    """

    def __init__(self, entity: str) -> None:
        super().__init__(f"unknown / unregistered entity: {entity!r}")
        self.entity = entity


@runtime_checkable
class IntentRepository(Protocol):
    """账本的持久化契约 (写入 / 生命周期流转 / effective 读取)."""

    def insert(self, record: IntentRecord, *, auto_apply: bool) -> InsertOutcome:
        """原子地写入一条 intent.

        实现需在单事务内完成: (PATCH+auto 时) 取 advisory 锁串行化 → 幂等检查
        (同 source 命中则复用既有 id, created=False) → INSERT
        (auto_apply 决定落 APPLIED+applied_at 还是 PROPOSED).
        """
        ...

    def confirm(self, user_id: str, intent_ids: Sequence[int]) -> int:
        """PROPOSED → APPLIED, 维护"一字段一条 live PATCH"不变量. 返回生效条数."""
        ...

    def reject(self, user_id: str, intent_ids: Sequence[int], reason: str = "") -> int:
        """PROPOSED/APPLIED → REJECTED. 返回条数."""
        ...

    def expire_before(
        self,
        cutoff: datetime,
        *,
        user_id: str | None = None,
        target_entity: str | None = None,
    ) -> list[str]:
        """把 applied_at < cutoff 的 live intent 标 EXPIRED. 返回受影响的 user_id 列表."""
        ...

    def purge_row(self, entity: str, user_id: str, row_id: int | str) -> int:
        """硬删某实体某行的全部 intent (彻底抹除该行的账本记忆). 返回删除条数. 多租户隔离.

        与 reject/expire (软流转, 留痕) 不同, 这是物理删除 —— 用于"删除该实体行"时连带
        清掉它名下所有记忆, 不留僵尸数据. 行内 superseded_by 自引用由 ON DELETE SET NULL
        兜住 (同批删除内的互引也安全).
        """
        ...

    def effective(
        self,
        entity: str,
        user_id: str,
        row_id: int | str,
        *,
        as_of: datetime | None = None,
    ) -> Row | None:
        """调 effective_<entity>_at(user_id, row_id, as_of) 合成截至某时点的真相."""
        ...

    def list_intents(
        self,
        entity: str,
        user_id: str,
        row_id: int | str,
        *,
        statuses: Sequence[str] | None = None,
    ) -> list[Row]:
        """列出某实体某行的原始 intent 流水 (不合成), 按时间升序. 多租户隔离.

        与 effective 互补: effective 合成"截至某刻的真相", 本方法返回构成它的每条
        原始 intent 行 (含 status / source_layer / source_quote / 各时间戳), 供上层
        画审计时间轴 + 逐字溯源. statuses 给定时只返回这些状态的行.
        """
        ...
