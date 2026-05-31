"""Intent 的核心类型与不可变记录 —— 纯 domain, 零 I/O 零框架.

4-kind 的语义与 DB CHECK 一一对应 (见 infrastructure/persistence/sql/001_core.sql
的 chk_patch_kind_shape):

* PATCH    — 改业务字段值. patch_json 必须含与 target_field 同名 key.
* ASSERT   — 用户陈述事实. patch_json 任意非空 object.
* ANNOTATE — 加注释. patch_json 必含字符串 annotation.
* FLAG     — 标疑. 必须 target_field + patch_json.flag_reason.

5 级 source_layer 权威度 (高→低), 决定 PATCH winner 仲裁的首要排序键.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Literal

Kind = Literal["PATCH", "ASSERT", "ANNOTATE", "FLAG"]
SourceLayer = Literal["USER_DIRECT", "L2_FORM", "L2_CHAT", "L2_VOICE", "AGENT_INFERENCE"]

KINDS: tuple[Kind, ...] = ("PATCH", "ASSERT", "ANNOTATE", "FLAG")
SOURCE_LAYERS: tuple[SourceLayer, ...] = (
    "USER_DIRECT",
    "L2_FORM",
    "L2_CHAT",
    "L2_VOICE",
    "AGENT_INFERENCE",
)


@dataclass(frozen=True, slots=True)
class IntentRecord:
    """跨持久化边界 (application → IntentRepository 端口) 的不可变写入契约.

    这是一条"已规范化、已校验、待落库"的 intent. 把它定义成显式 frozen dataclass
    而不是裸 dict, 是为了让持久化端口的输入契约可被类型检查、不可变、自文档化.
    """

    user_id: str
    kind: Kind
    target_entity: str
    patch_json: dict[str, Any]
    source_layer: SourceLayer
    source_table: str
    source_id: str
    reason: str = ""
    target_date: str | None = None
    target_row_id: str | None = None
    target_field: str | None = None
    source_quote: str | None = None
    confidence: float = 1.0
    extracted_by: str | None = None
    # 仅用于把别名规范化后的派生字段带出去 (normalize 可能改写 patch_json/target_field).
    _extra: dict[str, Any] = field(default_factory=dict, repr=False)

    def policy_view(self) -> dict[str, Any]:
        """投影成 AutoApplyPolicy.should_auto_apply 需要的最小 dict 输入."""
        return {
            "target_entity": self.target_entity,
            "kind": self.kind,
            "confidence": self.confidence,
        }
