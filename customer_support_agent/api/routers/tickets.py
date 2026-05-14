from __future__ import annotations
import logging
from typing import Any
from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException
from customer_support_agent.api.dependencies import (
    get_copilot,
    get_copilot_or_503,
    get_customers_repository,
    get_drafts_repository,
    get_tickets_repository,
)
from customer_support_agent.repositories.sqlite.customers import CustomersRepository
from customer_support_agent.repositories.sqlite.drafts import DraftsRepository
from customer_support_agent.repositories.sqlite.tickets import TicketsRepository
from customer_support_agent.schemas.api import GenerateDraftResponse, TicketCreateRequest, TicketResponse
from customer_support_agent.services.copilot_service import SupportCopilot
from customer_support_agent.services.draft_service import generate_and_store_background, generate_and_store_manual
logger = logging.getLogger(__name__)
router = APIRouter()


@router.post("/api/tickets", response_model=TicketResponse)
def create_ticket_route(
    payload: TicketCreateRequest,
    background_tasks: BackgroundTasks,
    customers_repo: CustomersRepository = Depends(get_customers_repository),
    tickets_repo: TicketsRepository = Depends(get_tickets_repository),
    drafts_repo: DraftsRepository = Depends(get_drafts_repository),
) -> dict[str, Any]:
    customer = customers_repo.create_or_get(email=str(payload.customer_email), name=payload.customer_name)
    ticket = tickets_repo.create(
        customer_id=customer["id"], subject=payload.subject,
        description=payload.description, priority=payload.priority,
    )

    if payload.auto_generate:
        background_tasks.add_task(
            generate_and_store_background,
            ticket["id"], tickets_repo, customers_repo, drafts_repo, get_copilot(), logger,
        )

    return {**ticket, "customer_email": customer["email"], "customer_name": customer.get("name")}


@router.get("/api/tickets", response_model=list[TicketResponse])
def list_tickets_route(tickets_repo: TicketsRepository = Depends(get_tickets_repository)) -> list[dict[str, Any]]:
    return tickets_repo.list()


@router.get("/api/tickets/{ticket_id}", response_model=TicketResponse)
def get_ticket_route(
    ticket_id: int,
    tickets_repo: TicketsRepository = Depends(get_tickets_repository),
) -> dict[str, Any]:
    ticket = tickets_repo.get_by_id(ticket_id)
    if not ticket:
        raise HTTPException(status_code=404, detail="Ticket not found")
    return ticket


@router.post("/api/tickets/{ticket_id}/generate-draft", response_model=GenerateDraftResponse)
def generate_draft_route(
    ticket_id: int,
    tickets_repo: TicketsRepository = Depends(get_tickets_repository),
    customers_repo: CustomersRepository = Depends(get_customers_repository),
    drafts_repo: DraftsRepository = Depends(get_drafts_repository),
    copilot: SupportCopilot = Depends(get_copilot_or_503),
) -> dict[str, Any]:
    ticket = tickets_repo.get_by_id(ticket_id)
    if not ticket:
        raise HTTPException(status_code=404, detail="Ticket not found")
    customer = customers_repo.get_by_id(ticket["customer_id"])
    if not customer:
        raise HTTPException(status_code=404, detail="Customer not found")

    try:
        draft = generate_and_store_manual(ticket_id, ticket, customer, drafts_repo, copilot)
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Failed to generate draft: {exc}") from exc

    return {"ticket_id": ticket_id, "draft": draft}
