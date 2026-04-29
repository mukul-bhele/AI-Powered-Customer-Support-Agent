"""
Draft service — orchestrates AI draft generation and serialisation.

Responsibilities:
  - generate_and_store_background()  → called from a FastAPI BackgroundTask
                                       (ticket just submitted, no copilot yet)
  - generate_and_store_manual()      → called synchronously when agent clicks
                                       "Generate Draft" in the UI
  - serialize_draft() / serialize_ticket() → shape DB dicts for API responses
"""
from __future__ import annotations

import json
import logging
from typing import Any, Callable

from customer_support_agent.repositories.sqlite.customers import CustomersRepository
from customer_support_agent.repositories.sqlite.drafts import DraftsRepository
from customer_support_agent.repositories.sqlite.tickets import TicketsRepository
from customer_support_agent.services.copilot_service import SupportCopilot


class DraftService:

    # ── Serialisers ───────────────────────────────────────────────────────────

    def serialize_draft(self, draft: dict[str, Any]) -> dict[str, Any]:
        """
        Convert a raw DB draft row into the shape expected by DraftResponse.

        `context_used` is stored as a JSON string in SQLite; we parse it here
        so the API returns a proper dict (not a string).
        """
        context_raw  = draft.get("context_used")
        context_data: dict[str, Any] | None = None

        if context_raw:
            try:
                context_data = json.loads(context_raw)
            except json.JSONDecodeError:
                # Malformed JSON — wrap raw value so we don't lose it
                context_data = {"raw": context_raw}

        return {
            "id":           draft["id"],
            "ticket_id":    draft["ticket_id"],
            "content":      draft["content"],
            "context_used": context_data,
            "status":       draft["status"],
            "created_at":   draft["created_at"],
        }

    def serialize_ticket(self, ticket: dict[str, Any]) -> dict[str, Any]:
        """Convert a raw DB ticket row (with JOINed customer fields) into TicketResponse shape."""
        return {
            "id":               ticket["id"],
            "customer_id":      ticket["customer_id"],
            "customer_email":   ticket["customer_email"],
            "customer_name":    ticket.get("customer_name"),
            "customer_company": ticket.get("customer_company"),
            "subject":          ticket["subject"],
            "description":      ticket["description"],
            "status":           ticket["status"],
            "priority":         ticket["priority"],
            "created_at":       ticket["created_at"],
            "updated_at":       ticket["updated_at"],
        }

    # ── Generation ────────────────────────────────────────────────────────────

    def generate_and_store_background(
        self,
        ticket_id: int,
        tickets_repo: TicketsRepository,
        customers_repo: CustomersRepository,
        drafts_repo: DraftsRepository,
        copilot_factory: Callable[[], SupportCopilot],
        logger: logging.Logger,
    ) -> dict[str, Any] | None:
        """
        Generate and store a draft as a background task.

        Called automatically after a ticket is created (when auto_generate=True).
        Uses a factory callable instead of a direct copilot instance so that
        the copilot is created inside the background thread, not the request thread.

        Returns None if the ticket or customer cannot be found.
        On any AI error, stores a fallback placeholder draft so the ticket
        still shows something in the inbox.
        """
        ticket = tickets_repo.get_by_id(ticket_id)
        if not ticket:
            return None

        customer = customers_repo.get_by_id(ticket["customer_id"])
        if not customer:
            return None

        try:
            copilot = copilot_factory()
            result  = copilot.generate_draft(ticket=ticket, customer=customer)
            draft_text, context = self._normalize_draft_result(result)

            return drafts_repo.create(
                ticket_id=ticket_id,
                content=draft_text,
                context_used=json.dumps(context),
                status="pending",
            )
        except Exception as exc:
            logger.exception("Background draft generation failed for ticket_id=%s", ticket_id)
            # Store a placeholder so the agent knows something went wrong
            return drafts_repo.create(
                ticket_id=ticket_id,
                content=(
                    "Automatic draft generation failed. "
                    "Configure AI keys and trigger manual draft generation."
                ),
                context_used=json.dumps(self._failed_context(str(exc))),
                status="failed",
            )

    def generate_and_store_manual(
        self,
        ticket_id: int,
        ticket: dict[str, Any],
        customer: dict[str, Any],
        drafts_repo: DraftsRepository,
        copilot: SupportCopilot,
    ) -> dict[str, Any]:
        """
        Generate and store a draft synchronously (agent-triggered).

        Unlike the background version, this raises exceptions so the
        router can return a proper HTTP 500 with an error message.
        """
        result     = copilot.generate_draft(ticket=ticket, customer=customer)
        draft_text, context = self._normalize_draft_result(result)

        return drafts_repo.create(
            ticket_id=ticket_id,
            content=draft_text,
            context_used=json.dumps(context),
            status="pending",
        )

    # ── Private helpers ───────────────────────────────────────────────────────

    def _normalize_draft_result(self, result: dict[str, Any]) -> tuple[str, dict[str, Any]]:
        """
        Extract draft text and context from the copilot's raw return value.

        If the copilot somehow returns empty text, substitute a safe
        fallback message and record the error in context.
        """
        draft_text = str(result.get("draft") or "").strip()
        context    = result.get("context_used") or {}

        if not isinstance(context, dict):
            context = {"raw": str(context)}

        if not draft_text:
            draft_text = (
                "Thanks for your message. We are reviewing your issue "
                "and will share a concrete update shortly."
            )
            context.setdefault("errors", []).append(
                "Copilot returned empty draft content; fallback text was used."
            )

        return draft_text, context

    @staticmethod
    def _failed_context(error_text: str) -> dict[str, Any]:
        """Build a minimal context dict to record a generation failure."""
        return {
            "version": 2,
            "signals": {
                "memory_hit_count":    0,
                "knowledge_hit_count": 0,
                "tool_call_count":     0,
                "tool_error_count":    1,
                "knowledge_sources":   [],
            },
            "highlights":     {"memory": [], "knowledge": [], "tools": []},
            "memory_hits":    [],
            "knowledge_hits": [],
            "tool_calls":     [],
            "errors":         [error_text],
        }
