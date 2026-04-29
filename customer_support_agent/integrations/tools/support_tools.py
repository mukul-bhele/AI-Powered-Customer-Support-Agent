"""
LangChain tools available to the AI support agent.
Each @tool function can be called by the agent during draft generation
to look up real data before writing a response. Tools return JSON strings
so the agent can parse and reason over the output.

Available tools:
  - lookup_customer_plan       → subscription tier and SLA hours
  - lookup_open_ticket_load    → how many open tickets the customer has
"""
from __future__ import annotations
import hashlib
import json
from langchain_core.tools import tool
from customer_support_agent.repositories.sqlite.customers import CustomersRepository
from customer_support_agent.repositories.sqlite.tickets import TicketsRepository

# ── Private helpers ───────────────────────────────────────────────────────────
def _stable_bucket(email: str, size: int) -> int:
    """
    Deterministically map an email to a bucket index (0 … size-1).
    Uses SHA-256 so the same email always gets the same bucket,
    making plan lookups consistent across runs without a real billing API.
    """
    digest = hashlib.sha256(email.strip().lower().encode("utf-8")).hexdigest()
    return int(digest, 16) % size

def _load_band(open_count: int) -> str:
    """Classify a customer's open-ticket count into a human-readable band."""
    if open_count <= 1:
        return "light"
    if open_count <= 3:
        return "moderate"
    return "heavy"


# ── Tools ─────────────────────────────────────────────────────────────────────
@tool
def lookup_customer_plan(customer_email: str) -> str:
    """Return structured subscription and SLA details for a customer email."""
    # Simulated plan catalogue (replace with a real billing API call)
    plans = [
        {"plan_tier": "free",       "sla_hours": 48, "priority_queue": False},
        {"plan_tier": "starter",    "sla_hours": 24, "priority_queue": False},
        {"plan_tier": "pro",        "sla_hours": 8,  "priority_queue": True},
        {"plan_tier": "enterprise", "sla_hours": 1,  "priority_queue": True},
    ]
    plan = plans[_stable_bucket(customer_email, len(plans))]

    return json.dumps({
        "tool":               "lookup_customer_plan",
        "customer_email":     customer_email,
        "summary":            (
            f"{customer_email} is on the {plan['plan_tier']} plan "
            f"with {plan['sla_hours']}h SLA."
        ),
        "details":            plan,
        "recommended_action": (
            "Use priority handling." if plan["priority_queue"] else "Use standard handling."
        ),
    })

@tool
def lookup_open_ticket_load(customer_email: str) -> str:
    """Return open ticket count and load band for a customer email."""
    customer = CustomersRepository().get_by_email(customer_email)

    if not customer:
        return json.dumps({
            "tool":               "lookup_open_ticket_load",
            "customer_email":     customer_email,
            "summary":            f"No customer record found for {customer_email}.",
            "details": {
                "customer_found": False,
                "open_tickets":   None,
                "load_band":      "unknown",
            },
            "recommended_action": "Ask agent to verify customer email before promising SLA.",
        })

    open_count = TicketsRepository().count_open_for_customer(customer_email)

    return json.dumps({
        "tool":               "lookup_open_ticket_load",
        "customer_email":     customer_email,
        "summary":            f"Customer {customer_email} has {open_count} open ticket(s).",
        "details": {
            "customer_found": True,
            "open_tickets":   open_count,
            "load_band":      _load_band(open_count),
        },
        "recommended_action": (
            "Acknowledge multiple ongoing issues."
            if open_count > 1 else
            "Handle as isolated incident."
        ),
    })


def get_support_tools() -> list:
    """Return the list of tools registered with the AI agent."""
    return [lookup_customer_plan, lookup_open_ticket_load]