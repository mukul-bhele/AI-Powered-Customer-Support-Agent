"""
FastAPI application factory.

`create_app()` is the entry point called by uvicorn:

    uvicorn customer_support_agent.api.app_factory:create_app --factory

Using a factory (instead of a module-level `app` variable) means we can
pass custom Settings in tests without touching environment variables.

Startup sequence (lifespan):
  1. ensure_directories() → create data/, chroma_rag/, chroma_mem0/ if missing
  2. init_db()            → create SQLite tables/triggers if they don't exist yet
"""
from __future__ import annotations

from contextlib import asynccontextmanager

from fastapi import FastAPI

from customer_support_agent.api.routers import (
    drafts_router,
    health_router,
    knowledge_router,
    memory_router,
    tickets_router,
)
from customer_support_agent.core.settings import Settings, ensure_directories, get_settings
from customer_support_agent.repositories.sqlite import init_db


def create_app(settings: Settings | None = None) -> FastAPI:
    """
    Build and return the FastAPI application.

    Args:
        settings: Optional custom Settings (useful in tests).
                  Defaults to settings loaded from .env.
    """
    resolved_settings = settings or get_settings()

    @asynccontextmanager
    async def lifespan(_: FastAPI):
        # Run once on startup before the first request is handled
        ensure_directories(resolved_settings)
        init_db()
        yield
        # (anything after yield runs on shutdown)

    app = FastAPI(title=resolved_settings.app_name, lifespan=lifespan)

    # Register all route groups
    app.include_router(health_router)
    app.include_router(tickets_router)
    app.include_router(drafts_router)
    app.include_router(knowledge_router)
    app.include_router(memory_router)

    return app
