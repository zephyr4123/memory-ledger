"""Auto-apply 风险矩阵 —— domain 策略, 零 I/O.

这是本系统区别于 mem0 / Zep 的"写风险闸门":
  * ASSERT / ANNOTATE / FLAG — 用户陈述 / 加注释 / 标疑, 低风险, auto-apply.
  * PATCH — 改业务字段, 高风险, 默认走 PROPOSED + 人工 banner 拍板.
  * 例外: 数据源校正类 PATCH (外部 API pull 的 raw 数据) 可显式列入矩阵 auto-apply.

矩阵是 (entity, kind) -> bool, 不在矩阵里的默认 False. confidence 是软门,
主决策权在矩阵. 高危写入在人确认前不进 effective view.
"""

from __future__ import annotations

from collections.abc import Iterable
from typing import Any

DEFAULT_THRESHOLD = 0.6

_LOW_RISK_KINDS: tuple[str, ...] = ("ASSERT", "ANNOTATE", "FLAG")


class AutoApplyPolicy:
    """(entity, kind) -> 是否 auto-apply, 叠加一个 confidence 阈值."""

    def __init__(
        self,
        rules: dict[tuple[str, str], bool] | Iterable[tuple[str, str]] | None = None,
        *,
        threshold: float = DEFAULT_THRESHOLD,
    ) -> None:
        # 允许传 set/iterable of (entity, kind) 当作"这些 auto-apply".
        if rules is None:
            normalized: dict[tuple[str, str], bool] = {}
        elif isinstance(rules, dict):
            normalized = dict(rules)
        else:
            normalized = dict.fromkeys(rules, True)
        self.rules = normalized
        self.threshold = threshold

    def should_auto_apply(self, intent: dict[str, Any]) -> bool:
        key = (intent.get("target_entity"), intent.get("kind"))
        if not self.rules.get(key, False):  # type: ignore[arg-type]
            return False
        try:
            confidence = float(intent.get("confidence", 0))
        except (TypeError, ValueError):
            return False
        return confidence >= self.threshold

    @classmethod
    def low_risk_for(
        cls, entities: Iterable[str], *, threshold: float = DEFAULT_THRESHOLD
    ) -> AutoApplyPolicy:
        """便捷构造: 给定实体集, 自动放行其 ASSERT/ANNOTATE/FLAG, PATCH 仍走 banner."""
        rules = {(ent, kind): True for ent in entities for kind in _LOW_RISK_KINDS}
        return cls(rules, threshold=threshold)
