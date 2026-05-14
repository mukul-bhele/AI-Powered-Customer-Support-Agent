from __future__ import annotations
from functools import lru_cache
from fastapi import HTTPException
from customer_support_agent.core.settings import Settings, get_settings
from customer_support_agent.repositories.sqlite.customers import CustomersRepository
from customer_support_agent.repositories.sqlite.drafts import DraftsRepository
from customer_support_agent.repositories.sqlite.tickets import TicketsRepository
from customer_support_agent.services.copilot_service import SupportCopilot

@lru_cache
def get_copilot() -> SupportCopilot:
    return SupportCopilot(settings=get_settings())

def get_copilot_or_503() -> SupportCopilot:
    try:
        return get_copilot()
    except Exception as exc:
        raise HTTPException(status_code=503, detail=f"Copilot unavailable: {exc}") from exc

def get_settings_dep() -> Settings: return get_settings()
def get_customers_repository() -> CustomersRepository: return CustomersRepository()
def get_tickets_repository() -> TicketsRepository: return TicketsRepository()
def get_drafts_repository() -> DraftsRepository: return DraftsRepository()
