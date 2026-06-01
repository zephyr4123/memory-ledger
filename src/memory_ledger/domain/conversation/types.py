"""Responder 输出的纯 domain 类型 —— 一次应答的产物, 落库前形态. 零 I/O.

系统的集成契约: 一次 LLM 调用同步产出 reply + 4 类 typed intent. 这里把"模型想写
什么"建模成不可变 domain 对象 (ProposedIntent / Response), 让 Responder 端口
(ports/responder.py) 说 domain 对象而不是裸 JSON —— wire JSON 的解析是真实
Responder 适配器的事, 不是端口的事.

ProposedIntent 是"未规范化、未校验"的提议; 进 application.MemoryLedger 后才走
normalize → validate → auto-apply 决策 → 落库. 与已落库的 IntentRecord
(domain/intents/types.py) 区分: 前者是模型输出, 后者是持久化输入契约.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from ..intents.types import Kind


@dataclass(frozen=True, slots=True)
class ProposedIntent:
    """模型想写的一条 intent (4-kind 之一), 尚未 normalize/validate."""

    kind: Kind
    target_entity: str
    patch_json: dict[str, Any]
    target_row_id: str | None = None
    target_field: str | None = None
    source_quote: str | None = None
    confidence: float = 1.0
    reason: str = ""


@dataclass(frozen=True, slots=True)
class Response:
    """一次应答的完整产物: 面向用户的 reply + 想写的 intent 序列.

    intents 是 4-kind 拍平的一个 tuple (kind 自身区分), 不拆 4 个数组 —— 下游 ledger
    已按 kind 分流, 拆开只会在 AgentLoop 里被重新合并. 单 tuple 让 loop 保持一次 fold.
    """

    reply: str
    intents: tuple[ProposedIntent, ...] = field(default_factory=tuple)
