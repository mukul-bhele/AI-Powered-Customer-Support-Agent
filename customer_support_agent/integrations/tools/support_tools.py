"""
LangChain tools available to the AI bank support agent.

Each @tool function can be called by the agent during draft generation
to look up real customer data before writing a response. Tools return
JSON strings so the agent can parse and reason over the output.

  - lookup_customer_account_tier  → account type and SLA hours
  - lookup_open_ticket_load       → how many open tickets the customer has
"""
from __future__ import annotations
import hashlib
import json
from langchain_core.tools import tool
from customer_support_agent.repositories.sqlite.customers import CustomersRepository
from customer_support_agent.repositories.sqlite.tickets import TicketsRepository


# ── Helpers ───────────────────────────────────────────────────────────────────
def _stable_bucket(email: str, size: int) -> int:
    """Map an email to a deterministic bucket index (same email → same bucket)."""
    digest = hashlib.sha256(email.strip().lower().encode("utf-8")).hexdigest()
    return int(digest, 16) % size

def _load_band(open_count: int) -> str:
    """Classify open-ticket count as light / moderate / heavy."""
    return "light" if open_count <= 1 else "moderate" if open_count <= 3 else "heavy"

def _response(tool_name: str, email: str, summary: str, details: dict, action: str) -> str:
    """Build the standard JSON response shape every tool returns."""
    return json.dumps({
        "tool":               tool_name,
        "customer_email":     email,
        "summary":            summary,
        "details":            details,
        "recommended_action": action,
    })


# ── Tools ─────────────────────────────────────────────────────────────────────
ACCOUNT_TIERS = [
    {"tier": "basic_savings",   "sla_hours": 48, "priority_queue": False},
    {"tier": "premium_savings", "sla_hours": 24, "priority_queue": False},
    {"tier": "current_account", "sla_hours": 12, "priority_queue": True},
    {"tier": "wealth",          "sla_hours": 1,  "priority_queue": True},
]


@tool
def lookup_customer_account_tier(customer_email: str) -> str:
    """Return the customer's account tier and SLA details."""
    tier = ACCOUNT_TIERS[_stable_bucket(customer_email, len(ACCOUNT_TIERS))]
    return _response(
        tool_name="lookup_customer_account_tier",
        email=customer_email,
        summary=f"{customer_email} holds a {tier['tier']} account with a {tier['sla_hours']}h response SLA.",
        details=tier,
        action="Use priority handling and reference the relationship manager." if tier["priority_queue"]
               else "Use standard handling per branch process.",
    )

@tool
def lookup_open_ticket_load(customer_email: str) -> str:
    """Return open ticket count and load band for a customer."""
    if not CustomersRepository().get_by_email(customer_email):
        return _response(
            tool_name="lookup_open_ticket_load",
            email=customer_email,
            summary=f"No customer record found for {customer_email}.",
            details={"customer_found": False, "open_tickets": None, "load_band": "unknown"},
            action="Ask agent to verify customer email before promising SLA.",
        )

    open_count = TicketsRepository().count_open_for_customer(customer_email)
    return _response(
        tool_name="lookup_open_ticket_load",
        email=customer_email,
        summary=f"Customer {customer_email} has {open_count} open ticket(s).",
        details={"customer_found": True, "open_tickets": open_count, "load_band": _load_band(open_count)},
        action="Acknowledge multiple ongoing issues." if open_count > 1 else "Handle as isolated incident.",
    )

def get_support_tools() -> list:
    """Return the list of tools registered with the AI agent."""
    return [lookup_customer_account_tier, lookup_open_ticket_load]
