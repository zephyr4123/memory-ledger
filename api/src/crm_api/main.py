"""crm_api FastAPI app —— 装配 + lifespan (建连接池 / 幂等迁移 / seed demo)。"""

from __future__ import annotations

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from .config import Settings
from .db import ensure_schema, make_pool
from .extraction import make_extractor
from .routes import chat, health, intents, people
from .seed import seed_demo


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    settings: Settings = app.state.settings
    pool = make_pool(settings.database_url)
    pool.open()
    pool.wait(timeout=15.0)
    with pool.connection() as conn:
        ensure_schema(conn)
        seed_demo(conn, settings.user_id)
    app.state.pool = pool
    app.state.extractor = make_extractor(settings)
    try:
        yield
    finally:
        pool.close()


def create_app(settings: Settings | None = None) -> FastAPI:
    settings = settings or Settings.from_env()
    app = FastAPI(title="memory-ledger CRM API", version="0.1.0", lifespan=lifespan)
    app.state.settings = settings
    app.add_middleware(
        CORSMiddleware,
        allow_origins=list(settings.cors_origins),
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )
    for router in (health.router, chat.router, people.router, intents.router):
        app.include_router(router, prefix="/api")
    return app


app = create_app()
