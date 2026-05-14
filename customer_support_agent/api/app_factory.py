from __future__ import annotations
from contextlib import asynccontextmanager
from fastapi import FastAPI
from customer_support_agent.api.routers import (
    drafts_router, health_router, knowledge_router, memory_router, tickets_router,
)
from customer_support_agent.core.settings import Settings, ensure_directories, get_settings
from customer_support_agent.repositories.sqlite import init_db

def create_app(settings: Settings | None = None) -> FastAPI:
    settings = settings or get_settings()
    @asynccontextmanager
    async def lifespan(_: FastAPI):
        ensure_directories(settings)
        init_db()
        yield

    app = FastAPI(title=settings.app_name, lifespan=lifespan)
    for r in (health_router, tickets_router, drafts_router, knowledge_router, memory_router):
        app.include_router(r)
    return app
