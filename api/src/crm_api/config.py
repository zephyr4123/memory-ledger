"""crm_api 配置 —— 全部从环境变量读, 集中成一个不可变 Settings.

LLM 走 LiteLLM 统一接入: 用 LLM_MODEL / LLM_API_KEY / LLM_BASE_URL 三个 env 即可
接任意模型 (DeepSeek / OpenAI / 任意 OpenAI 兼容端点 / Anthropic ...), 不绑死某家。
"""

from __future__ import annotations

import os
from dataclasses import dataclass

_DEFAULT_DSN = "postgresql://memory_ledger:memory_ledger@localhost:5432/memory_ledger"
_DEFAULT_ORIGINS = "http://localhost:5173,http://localhost:4173,http://localhost"
# LiteLLM 路由串: deepseek/ 是 provider 前缀, 真正发给 API 的 model 名是 deepseek-v4-pro。
_DEFAULT_MODEL = "deepseek/deepseek-v4-pro"


@dataclass(frozen=True, slots=True)
class Settings:
    database_url: str
    llm_model: str
    llm_api_key: str | None
    llm_base_url: str | None
    user_id: str
    cors_origins: tuple[str, ...]

    @property
    def llm_enabled(self) -> bool:
        """有 key 才是真 LLM (live); 否则回退离线 mock (degraded, 仅供启动/CI)。"""
        return bool(self.llm_api_key)

    @classmethod
    def from_env(cls) -> Settings:
        origins = os.environ.get("CORS_ORIGINS", _DEFAULT_ORIGINS)
        return cls(
            database_url=os.environ.get("DATABASE_URL", _DEFAULT_DSN),
            llm_model=(os.environ.get("LLM_MODEL") or "").strip() or _DEFAULT_MODEL,
            llm_api_key=(os.environ.get("LLM_API_KEY") or "").strip() or None,
            llm_base_url=(os.environ.get("LLM_BASE_URL") or "").strip() or None,
            user_id=os.environ.get("CRM_USER_ID", "u1"),
            cors_origins=tuple(o.strip() for o in origins.split(",") if o.strip()),
        )
