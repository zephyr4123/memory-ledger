"""工具注册表 —— 装饰器 + 注册表 (便于扩展/维护新工具).

设计目标: 加一把新工具 = 写一个被 `@tool(...)` 装饰的函数即可, 自动进 schema、自动可被
agent loop 调度, 无需改 responder。每个 handler 签名 `(ctx: ToolContext, **kwargs) -> Any`,
返回 JSON 可序列化结果 (会被回灌给模型)。
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from typing import Any

from .context import ToolContext


@dataclass(frozen=True)
class _Tool:
    name: str
    description: str
    parameters: dict[str, Any]  # OpenAI function-calling JSON schema
    handler: Callable[..., Any]


_REGISTRY: dict[str, _Tool] = {}


def tool(
    name: str, description: str, parameters: dict[str, Any]
) -> Callable[[Callable[..., Any]], Callable[..., Any]]:
    """把一个函数注册成 agent 可调的工具。"""

    def deco(fn: Callable[..., Any]) -> Callable[..., Any]:
        _REGISTRY[name] = _Tool(name=name, description=description, parameters=parameters, handler=fn)
        return fn

    return deco


def openai_schemas(names: list[str] | None = None) -> list[dict[str, Any]]:
    """导出给 LiteLLM 的 tools= 列表 (OpenAI function 格式)。names=None 取全部。"""
    items = (
        list(_REGISTRY.values())
        if names is None
        else [_REGISTRY[n] for n in names if n in _REGISTRY]
    )
    return [
        {
            "type": "function",
            "function": {"name": t.name, "description": t.description, "parameters": t.parameters},
        }
        for t in items
    ]


def dispatch(name: str, args: dict[str, Any] | None, ctx: ToolContext) -> Any:
    """按名字执行工具。未知工具/执行异常都返回 {error} 而非抛出 —— 不让单个工具崩掉整轮。"""
    t = _REGISTRY.get(name)
    if t is None:
        return {"error": f"没有名为 {name} 的工具"}
    try:
        return t.handler(ctx, **(args or {}))
    except TypeError as e:  # 模型传了非法参数名/缺参
        return {"error": f"工具 {name} 参数不对: {e}"}
    except Exception as e:  # noqa: BLE001 — 工具内任何错都降级成可回灌的结果
        return {"error": f"工具 {name} 执行出错: {e}"}
