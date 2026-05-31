"""持久化序列化 —— 把 patch_json (dict) 编码成可塞进 ``%s::jsonb`` 的 JSON 文本.

JSON 编码本身是 stdlib (纯), 但"为入库而编码"是持久化职责, 故归 infrastructure.
"""

from __future__ import annotations

import json
from datetime import date, datetime
from typing import Any


def to_jsonb(obj: Any) -> str:
    """编码成 jsonb 入库用的 JSON 文本 (ensure_ascii=False 保中文可读)."""
    return json.dumps(obj, ensure_ascii=False, default=_json_default)


def _json_default(o: Any) -> str:
    if isinstance(o, (date, datetime)):
        return o.isoformat()
    raise TypeError(f"not JSON serializable: {type(o)!r}")
