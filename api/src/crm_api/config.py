"""crm_api 配置 —— 全部从环境变量读, 集中成一个不可变 Settings.

集中读 env 的收益: 路由/依赖不直接摸 os.environ, 可测、可注入、口径单一。
"""

from __future__ import annotations

import os
from dataclasses import dataclass

_DEFAULT_DSN = "postgresql://memory_ledger:memory_ledger@localhost:5432/memory_ledger"
_DEFAULT_ORIGINS = "http://localhost:5173,http://localhost:4173,http://localhost"


@dataclass(frozen=True, slots=True)
class Settings:
    database_url: str
    anthropic_api_key: str | None
    model: str
    user_id: str
    cors_origins: tuple[str, ...]

    @property
    def llm_enabled(self) -> bool:
        """有 key 才是真 LLM (live); 否则回退离线 mock (degraded, 仅供启动/CI)。"""
        return bool(self.anthropic_api_key)

    @classmethod
    def from_env(cls) -> Settings:
        origins = os.environ.get("CORS_ORIGINS", _DEFAULT_ORIGINS)
        return cls(
            database_url=os.environ.get("DATABASE_URL", _DEFAULT_DSN),
            anthropic_api_key=(os.environ.get("ANTHROPIC_API_KEY") or "").strip() or None,
            model=os.environ.get("MEMORY_LEDGER_MODEL", "claude-sonnet-4-6"),
            user_id=os.environ.get("CRM_USER_ID", "u1"),
            cors_origins=tuple(o.strip() for o in origins.split(",") if o.strip()),
        )
