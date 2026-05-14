"""
Draft service — generates AI drafts and stores them in the DB.

  generate_and_store_background() → background task after ticket creation
  generate_and_store_manual()     → synchronous call from the generate-draft endpoint
"""
from __future__ import annotations

import logging
from typing import Any

from customer_support_agent.repositories.sqlite.customers import CustomersRepository
from customer_support_agent.repositories.sqlite.drafts import DraftsRepository
from customer_support_agent.repositories.sqlite.tickets import TicketsRepository
from customer_support_agent.services.copilot_service import SupportCopilot


def generate_and_store_background(
    ticket_id: int,
    tickets_repo: TicketsRepository,
    customers_repo: CustomersRepository,
    drafts_repo: DraftsRepository,
    copilot: SupportCopilot,
    logger: logging.Logger,
) -> dict[str, Any] | None:
    """Generate and store a draft in the background. Stores a failed placeholder if copilot raises."""
    ticket = tickets_repo.get_by_id(ticket_id)
    customer = customers_repo.get_by_id(ticket["customer_id"]) if ticket else None
    if not ticket or not customer:
        return None

    try:
        result = copilot.generate_draft(ticket=ticket, customer=customer)
        return drafts_repo.create(ticket_id=ticket_id, content=str(result["draft"]).strip(), status="pending")
    except Exception:
        logger.exception("Background draft generation failed for ticket_id=%s", ticket_id)
        return drafts_repo.create(
            ticket_id=ticket_id,
            content="Automatic draft generation failed. Configure AI keys and try generating manually.",
            status="failed",
        )

def generate_and_store_manual(
    ticket_id: int,
    ticket: dict[str, Any],
    customer: dict[str, Any],
    drafts_repo: DraftsRepository,
    copilot: SupportCopilot,
) -> dict[str, Any]:
    """Generate and store a draft synchronously. Raises on failure so the router returns HTTP 500."""
    result = copilot.generate_draft(ticket=ticket, customer=customer)
    return drafts_repo.create(ticket_id=ticket_id, content=str(result["draft"]).strip(), status="pending")