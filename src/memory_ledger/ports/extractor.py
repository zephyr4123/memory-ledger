"""Extractor 端口 —— 把"一次 model 调用"做成可替换的反转点.

与 IntentRepository / DBAdapter 同理: application 的 AgentLoop 只认这个抽象, 真实
模型适配器 (LlmExtractor, 解析 wire JSON) 与确定性 MockExtractor (脚本驱动 demo/CI)
都实现它. 端口说 domain 对象 (Extraction), 不说 JSON —— JSON 解析是适配器内部的事.

只依赖 domain (extraction 子域), 不依赖 application/infrastructure —— 满足单向依赖铁律.
"""

from __future__ import annotations

from typing import Protocol, runtime_checkable

from ..domain.extraction import Extraction


@runtime_checkable
class Extractor(Protocol):
    """从一句话 (+ 当前 snapshot 上下文) 抽出 reply + 想写的 intent 序列."""

    def extract(self, *, utterance: str, snapshot: str, turn: int) -> Extraction:
        """返回一次"model 调用"的产物.

        snapshot 是本轮注入模型的上下文 (真实适配器会用它; mock 可忽略).
        turn 是 0-based 轮次序号 (脚本化 mock 用它定位).
        """
        ...
