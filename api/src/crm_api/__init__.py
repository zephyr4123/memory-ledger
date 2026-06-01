"""crm_api —— memory-ledger Personal-CRM 参考应用的 FastAPI 后端.

它是库的一个**驱动适配器**(与 CLI 平级): 把 memory-ledger 的账本能力 + 一个真
LLM responder 编排成对话式 HTTP API。库核心保持 LLM 无关; 真 LLM 只是 `Responder`
端口的具体实现 (经 LiteLLM 接任意 provider), 住在这里 (`crm_api.responder`)。
"""

from __future__ import annotations

__version__ = "0.1.0"
