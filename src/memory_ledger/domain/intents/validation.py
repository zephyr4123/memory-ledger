"""按 kind 校验 intent 结构 —— 纯函数, 零 I/O.

与 DB 的 chk_patch_kind_shape CHECK 等价, 但提前在 domain 层给出可读错误,
而不是等 DB 抛 "violates check constraint" 这种无信息量的报错.
"""

from __future__ import annotations

from typing import Any

from .types import KINDS


class IntentShapeError(ValueError):
    """intent 结构不合法 (kind 与 patch_json/target_field 不匹配)."""


def validate_intent_shape(intent: dict[str, Any]) -> None:
    """按 kind 校验 intent 结构. 不合法 raise IntentShapeError."""
    kind = intent.get("kind")
    patch = intent.get("patch_json") or {}
    field = intent.get("target_field")

    if kind not in KINDS:
        raise IntentShapeError(f"unknown intent kind: {kind!r}")
    if not isinstance(patch, dict):
        raise IntentShapeError("patch_json must be an object/dict")

    if kind == "PATCH":
        if not field:
            raise IntentShapeError("PATCH requires target_field")
        if field not in patch:
            raise IntentShapeError(
                f"PATCH: target_field {field!r} must be a key in patch_json"
            )
    elif kind == "ASSERT":
        if not patch:
            raise IntentShapeError("ASSERT requires non-empty patch_json")
    elif kind == "ANNOTATE":
        if "annotation" not in patch:
            raise IntentShapeError("ANNOTATE requires 'annotation' key in patch_json")
        if not isinstance(patch["annotation"], str):
            raise IntentShapeError("ANNOTATE: annotation must be a string")
    elif kind == "FLAG":
        if not field:
            raise IntentShapeError("FLAG requires target_field")
        if "flag_reason" not in patch:
            raise IntentShapeError("FLAG requires 'flag_reason' key in patch_json")
