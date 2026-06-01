"""tools —— 小本的工具集(装饰器 + 注册表)。

import 本包即完成所有工具注册(contacts 里的 @tool 在导入时执行)。
"""

from __future__ import annotations

from . import contacts as contacts  # noqa: F401 — 导入即注册 @tool
from .context import ToolContext
from .registry import dispatch, openai_schemas, tool

__all__ = ["ToolContext", "dispatch", "openai_schemas", "tool"]
