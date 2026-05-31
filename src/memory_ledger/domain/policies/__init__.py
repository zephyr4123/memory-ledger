"""policies 子域 —— 写风险 / 生命周期等业务策略.

目前只有 auto-apply 风险矩阵; confidence 校准、置信度衰减、按属性 TTL 等
策略后续都归到这里 (见 roadmap).
"""

from __future__ import annotations

from .auto_apply import DEFAULT_THRESHOLD, AutoApplyPolicy

__all__ = ["DEFAULT_THRESHOLD", "AutoApplyPolicy"]
