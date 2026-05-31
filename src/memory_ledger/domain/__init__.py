"""domain —— 纯业务核心. 零 I/O、零框架、不依赖任何其他层.

子域:
  * intents   — 4-kind 类型 (IntentRecord)、别名规范化、形状校验
  * policies  — 写风险矩阵 (AutoApplyPolicy) 等业务策略
  * snapshot  — system-prompt 注入安全清洗与定界渲染
"""

from __future__ import annotations

from .intents import (
    KINDS,
    SOURCE_LAYERS,
    IntentRecord,
    IntentShapeError,
    Kind,
    SourceLayer,
    normalize_intent,
    validate_intent_shape,
)
from .policies import DEFAULT_THRESHOLD, AutoApplyPolicy
from .snapshot import render_snapshot, sanitize_text

__all__ = [
    "DEFAULT_THRESHOLD",
    "KINDS",
    "SOURCE_LAYERS",
    "AutoApplyPolicy",
    "IntentRecord",
    "IntentShapeError",
    "Kind",
    "SourceLayer",
    "normalize_intent",
    "render_snapshot",
    "sanitize_text",
    "validate_intent_shape",
]
