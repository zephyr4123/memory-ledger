"""ToolContext —— 一轮对话里所有工具共享的运行上下文.

把"这次是谁、看哪个联系人、用哪条 DB 连接、暂存了哪些待写 intent"收口成一个对象,
经 registry.dispatch 注入每个工具 handler。读工具用 ledger/conn 查;写工具往
staged_intents 暂存(真正落盘在 chat 路由 loop 结束后统一做, 沿用 banner 闸门逻辑)。
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from memory_ledger import MemoryLedger, ProposedIntent


@dataclass
class ToolContext:
    conn: Any  # 借出的 psycopg 连接 (read 工具的裸 SQL 用, 如列联系人 id)
    ledger: MemoryLedger  # 装配好的账本 (effective / history)
    user_id: str  # 多租户键 (写死取自 settings)
    focus_person_id: int  # 当前对话焦点联系人
    staged_intents: list[ProposedIntent] = field(default_factory=list)  # 写工具暂存, 待路由落盘
