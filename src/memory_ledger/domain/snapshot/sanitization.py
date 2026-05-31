"""不可信文本清洗 —— 纯函数, 零 I/O.

effective view 里的用户/LLM 文本拼进 system prompt 时是不可信的 (二阶 prompt
injection / 记忆投毒): 用户可在一条 annotation 里写 "IGNORE PREVIOUS
INSTRUCTIONS ...", 它会 auto-apply 并逐字进入未来每一轮 system prompt.
sanitize_text 去掉伪造定界/角色标记与危险不可见字符, 并截断超长内容.
"""

from __future__ import annotations

import re
import unicodedata

# 用户内容里若出现这些, 会被中和 (它们是我们自己定界/角色标记的形态)
_SPOOF_PATTERNS = re.compile(
    r"(?im)^\s*(system|assistant|user)\s*:|</?context_snapshot>|```",
)
# 文本方向覆盖等危险不可见字符
_DANGEROUS_INVISIBLE = {
    "‪", "‫", "‬", "‭", "‮",  # bidi overrides
    "⁦", "⁧", "⁨", "⁩",            # bidi isolates
    "﻿",                                          # zero-width no-break
}


def sanitize_text(text: str | None, *, max_len: int = 500) -> str:
    """清洗一段要进 prompt 的不可信文本."""
    if not text:
        return ""
    # 1. 去危险不可见字符
    cleaned = "".join(ch for ch in text if ch not in _DANGEROUS_INVISIBLE)
    # 2. 去 C0 控制符 (保留 \n \t)
    cleaned = "".join(
        ch for ch in cleaned if ch in ("\n", "\t") or unicodedata.category(ch)[0] != "C"
    )
    # 3. 中和伪造定界/角色标记
    cleaned = _SPOOF_PATTERNS.sub("[redacted]", cleaned)
    # 4. 截断
    cleaned = cleaned.strip()
    if len(cleaned) > max_len:
        cleaned = cleaned[:max_len].rstrip() + "…"
    return cleaned
