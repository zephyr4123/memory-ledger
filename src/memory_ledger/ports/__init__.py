"""ports —— 六边形架构的边 (抽象接口). 无具体实现.

  * DBAdapter        — 驱动级低层 SQL 执行器 (换 driver 的缝)
  * IntentRepository — 面向 domain 的持久化边界 (application 依赖它)
"""

from __future__ import annotations

from .database import DBAdapter, Row
from .repository import InsertOutcome, IntentRepository

__all__ = ["DBAdapter", "InsertOutcome", "IntentRepository", "Row"]
