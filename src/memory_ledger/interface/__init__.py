"""interface —— 对外入口 (driving adapters): CLI 等. 在组合根接线后驱动 application."""

from __future__ import annotations

from .cli import main

__all__ = ["main"]
