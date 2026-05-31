"""snapshot 子域 —— 注入安全清洗 + 定界渲染 (纯文本逻辑)."""

from __future__ import annotations

from .rendering import render_snapshot
from .sanitization import sanitize_text

__all__ = ["render_snapshot", "sanitize_text"]
