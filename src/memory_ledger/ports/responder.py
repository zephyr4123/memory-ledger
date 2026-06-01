"""Responder 端口 —— 把"一次 model 调用"做成可替换的反转点.

Responder 是系统里唯一的 AI: 它**同步**应答用户 (reply), 并在同一次调用里产出想落盘
的结构化 intent。与 IntentRepository / DBAdapter 同理, application 的 AgentLoop 只认
这个抽象, 真实模型适配器 (LiteLLMResponder, 解析 wire JSON) 与确定性 MockResponder
(脚本驱动 demo/CI) 都实现它。端口说 domain 对象 (Response), 不说 JSON —— JSON 解析
是适配器内部的事。

命名: 不叫 Extractor —— 它不是后台异步抽取器, 而是随用户输入同步应答的对话 AI。

只依赖 domain (conversation 子域), 不依赖 application/infrastructure —— 满足单向依赖铁律。
"""

from __future__ import annotations

from typing import Protocol, runtime_checkable

from ..domain.conversation import Response


@runtime_checkable
class Responder(Protocol):
    """从一句话 (+ 当前 snapshot 上下文) 同步应答: reply + 想写的 intent 序列."""

    def respond(self, *, utterance: str, snapshot: str, turn: int) -> Response:
        """返回一次"model 调用"的产物 (reply + intents)。

        snapshot 是本轮注入模型的记忆上下文 (真实适配器会用它; mock 可忽略)。
        turn 是 0-based 轮次序号 (脚本化 mock 用它定位)。
        """
        ...
