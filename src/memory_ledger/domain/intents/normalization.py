"""字段/值别名规范化 —— 纯函数, 零 I/O.

LLM 经常输出 ``deadline`` 而不是 canonical 列名 ``due_date``, 或 enum 口语值
``done`` 而不是 ``completed``. 这里把它们映射回 canonical, 让下游 (校验 / 落库)
只面对干净的字段名与值.
"""

from __future__ import annotations

from typing import Any


def normalize_intent(
    intent: dict[str, Any],
    *,
    field_aliases: dict[str, str] | None = None,
    value_aliases: dict[str, dict[str, str]] | None = None,
) -> dict[str, Any]:
    """把 LLM 常用的字段/值别名规范化到 DB canonical 名. 返回新 dict, 不改原始."""
    field_aliases = field_aliases or {}
    value_aliases = value_aliases or {}
    out = dict(intent)

    # 1. target_field 别名 → canonical, 同步搬动 patch_json 里的 key
    raw_field = out.get("target_field")
    if raw_field and raw_field in field_aliases:
        canonical = field_aliases[raw_field]
        out["target_field"] = canonical
        patch = dict(out.get("patch_json") or {})
        if raw_field in patch and canonical not in patch:
            patch[canonical] = patch.pop(raw_field)
        out["patch_json"] = patch

    # 2. patch_json 内枚举值别名 → canonical
    field = out.get("target_field")
    patch = out.get("patch_json") or {}
    if field and field in value_aliases and field in patch:
        v = patch[field]
        if isinstance(v, str) and v in value_aliases[field]:
            patch = dict(patch)
            patch[field] = value_aliases[field][v]
            out["patch_json"] = patch

    return out
