"""
FastAPI dependency injection.

Each function here is used with FastAPI's `Depends(...)` mechanism.
FastAPI calls them automatically and injects the returned object into
the route handler — keeping routes free of construction logic.

  get_copilot()          → singleton SupportCopilot (cached after first call)
  get_copilot_or_503()   → same, but returns HTTP 503 if the copilot fails to init
  get_*_repository()     → fresh repository instance per request (lightweight)
  get_draft_service()    → fresh DraftService per request
  get_knowledge_service()→ fresh KnowledgeService per request (needs Settings)
"""
from __future__ import annotations

from functools import lru_cache

from fastapi import Depends, HTTPException

from customer_support_agent.core.settings import Settings, get_settings
from customer_support_agent.repositories.sqlite.customers import CustomersRepository
from customer_support_agent.repositories.sqlite.drafts import DraftsRepository
from customer_support_agent.repositories.sqlite.tickets import TicketsRepository
from customer_support_agent.services.copilot_service import SupportCopilot
from customer_support_agent.services.draft_service import DraftService
from customer_support_agent.services.knowledge_service import KnowledgeService


@lru_cache
def get_copilot() -> SupportCopilot:
    """
    Return the application-wide SupportCopilot instance.

    @lru_cache means this is constructed once on first call and reused
    for every subsequent request — important because the agent loads
    models and opens connections at startup.
    """
    return SupportCopilot(settings=get_settings())


def get_copilot_or_503() -> SupportCopilot:
    """
    Like get_copilot(), but converts initialisation errors to HTTP 503.

    Use this on routes where the copilot is strictly required
    (e.g. generate-draft). Routes that only need the copilot
    optionally (e.g. accept draft) can fall back to get_copilot().
    """
    try:
        return get_copilot()
    except Exception as exc:
        raise HTTPException(status_code=503, detail=f"Copilot unavailable: {exc}") from exc


def get_settings_dep() -> Settings:
    """Expose Settings as a FastAPI dependency (needed by KnowledgeService)."""
    return get_settings()


def get_customers_repository() -> CustomersRepository:
    return CustomersRepository()


def get_tickets_repository() -> TicketsRepository:
    return TicketsRepository()


def get_drafts_repository() -> DraftsRepository:
    return DraftsRepository()


def get_draft_service() -> DraftService:
    return DraftService()


def get_knowledge_service(settings: Settings = Depends(get_settings_dep)) -> KnowledgeService:
    return KnowledgeService(settings=settings)
