"""intents 子域 —— 4-kind 类型、规范化、形状校验."""

from __future__ import annotations

from .normalization import normalize_intent
from .types import (
    KINDS,
    SOURCE_LAYERS,
    IntentRecord,
    Kind,
    SourceLayer,
)
from .validation import IntentShapeError, validate_intent_shape

__all__ = [
    "KINDS",
    "SOURCE_LAYERS",
    "IntentRecord",
    "IntentShapeError",
    "Kind",
    "SourceLayer",
    "normalize_intent",
    "validate_intent_shape",
]
