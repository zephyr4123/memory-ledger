"""FastAPI 依赖 —— 从 app.state 取装配好的单例 + per-request 借连接.

路由不直接摸 os.environ / 全局, 全部经依赖注入 → 可测 (dependency_overrides 注入
fake responder / 指向测试库)。
"""

from __future__ import annotations

from collections.abc import Iterator
from typing import Any

from fastapi import Request

from .config import Settings
from .responder import TurnResponder


def get_settings(request: Request) -> Settings:
    settings: Settings = request.app.state.settings
    return settings


def get_responder(request: Request) -> TurnResponder:
    responder: TurnResponder = request.app.state.responder
    return responder


def get_conn(request: Request) -> Iterator[Any]:
    """从连接池借一条连接, 请求结束归还 (yield 依赖的标准用法)。"""
    with request.app.state.pool.connection() as conn:
        yield conn
