from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException

from customer_support_agent.api.dependencies import get_copilot, get_drafts_repository, get_tickets_repository
from customer_support_agent.repositories.sqlite.drafts import DraftsRepository
from customer_support_agent.repositories.sqlite.tickets import TicketsRepository
from customer_support_agent.schemas.api import DraftResponse, DraftUpdateRequest


router = APIRouter()


@router.get("/api/drafts/{ticket_id}", response_model=DraftResponse)
def get_draft_route(
    ticket_id: int,
    drafts_repo: DraftsRepository = Depends(get_drafts_repository),
) -> dict:
    draft = drafts_repo.get_latest_for_ticket(ticket_id)
    if not draft:
        raise HTTPException(status_code=404, detail="Draft not found")
    return draft


@router.patch("/api/drafts/{draft_id}", response_model=DraftResponse)
def update_draft_route(
    draft_id: int,
    payload: DraftUpdateRequest,
    drafts_repo: DraftsRepository = Depends(get_drafts_repository),
    tickets_repo: TicketsRepository = Depends(get_tickets_repository),
) -> dict:
    if not drafts_repo.get_by_id(draft_id):
        raise HTTPException(status_code=404, detail="Draft not found")

    updated = drafts_repo.update(draft_id=draft_id, content=payload.content, status=payload.status)
    if not updated:
        raise HTTPException(status_code=500, detail="Failed to update draft")

    # On accept: resolve ticket + save resolution to memory (best-effort)
    if payload.status == "accepted":
        relation = drafts_repo.get_ticket_and_customer_by_draft(draft_id)
        if relation:
            tickets_repo.set_status(relation["ticket_id"], "resolved")
            try:
                get_copilot().save_accepted_resolution(
                    customer_email=relation["customer_email"],
                    ticket_subject=relation["subject"],
                    ticket_description=relation["description"],
                    draft_content=updated["content"],
                )
            except Exception:
                pass  # Memory save failure shouldn't block draft acceptance

    return updated
