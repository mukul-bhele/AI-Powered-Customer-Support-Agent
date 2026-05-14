"""
Support Copilot — the core AI agent for bank customer support.
Flow: search memory → search KB → run agent → LLM fallback → template fallback.
"""
from __future__ import annotations
import json
from typing import Any
from langchain.agents import create_agent
from langchain_core.messages import AIMessage, BaseMessage, HumanMessage, SystemMessage, ToolMessage
from langchain_groq import ChatGroq
from langgraph.checkpoint.memory import InMemorySaver
from customer_support_agent.core.settings import Settings
from customer_support_agent.integrations.memory.mem0_store import CustomerMemoryStore
from customer_support_agent.integrations.rag.chroma_kb import KnowledgeBaseService
from customer_support_agent.integrations.tools.support_tools import get_support_tools

def _dedupe(hits: list[dict]) -> list[dict]:
    seen, result = set(), []
    for h in hits:
        text = str(h.get("memory", "")).strip().lower()
        if text and text not in seen:
            seen.add(text)
            result.append(h)
    return result


class SupportCopilot:
    def __init__(self, settings: Settings):
        if not settings.groq_api_key:
            raise RuntimeError("GROQ_API_KEY is missing. Add it to .env.")
        self._settings = settings
        self._llm = ChatGroq(model=settings.groq_model, groq_api_key=settings.groq_api_key,
                             temperature=settings.llm_temperature)
        self._agent = create_agent(model=self._llm, tools=get_support_tools(),
                                   checkpointer=InMemorySaver(), name="support_copilot_agent")
        self.rag = KnowledgeBaseService(settings=settings)

        self._memory_error: str | None = None
        try:
            self.memory = CustomerMemoryStore(settings=settings)
        except Exception as exc:
            self._memory_error = str(exc)

    # ── Main entry point ──────────────────────────────────────────────────────
    def generate_draft(self, ticket: dict, customer: dict) -> dict:
        agent_output = self._agent.invoke(
            {"messages": [SystemMessage(content=self._system_prompt()),
                          HumanMessage(content=self._user_prompt(ticket, customer))]},
            config={"configurable": {"thread_id": f"ticket::{ticket.get('id', customer['email'])}"},
                    "recursion_limit": 40},
        )
        draft_text, tool_summaries = self._parse_agent_output(agent_output)
       
        if not draft_text:
            draft_text = self._llm_fallback(ticket, customer, tool_summaries)
        if not draft_text:
            draft_text = self._template_fallback(ticket, customer, tool_summaries)
        return {"draft": draft_text}

    # ── Memory ────────────────────────────────────────────────────────────────

    def list_customer_memories(self, customer_email: str, limit: int = 20) -> list[dict]:
        """Return all stored memories for a customer."""
        hits = self.memory.list_memories(user_id=customer_email.strip().lower(), limit=limit)
        return _dedupe(hits)[:limit]

    def search_customer_memories(self, customer_email: str, query: str, limit: int = 10) -> list[dict]:
        """Semantic search within a customer's stored memories."""
        if self._memory_error:
            return []
        email = customer_email.strip().lower()
        return _dedupe(self.memory.search(query=query, user_id=email, limit=self._settings.mem0_top_k))[:limit]

    def save_accepted_resolution(self, customer_email: str, ticket_subject: str,
                                 ticket_description: str, draft_content: str) -> None:
        self.memory.add_resolution(
            user_id=customer_email.strip().lower(),
            ticket_subject=ticket_subject,
            ticket_description=ticket_description,
            accepted_draft=draft_content,
        )

    # ── Prompts ───────────────────────────────────────────────────────────────
    @staticmethod
    def _system_prompt() -> str:
        return ("You are an AI copilot for bank customer support agents.\n"
                "Write concise, empathetic, and actionable draft replies.\n"
                "Call tools to check account/ticket load info when needed.\n"
                "Rules: start with empathy, give clear next steps, stay under 180 words.")
   
    @staticmethod
    def _user_prompt(ticket: dict, customer: dict) -> str:
        return (f"Customer: {customer.get('name') or 'Unknown'} ({customer['email']})\n"
                f"Subject:  {ticket['subject']}\n"
                f"Priority: {ticket.get('priority', 'medium')}\n\n"
                f"{ticket['description']}\n\n"
                f"Write a draft reply. Use tools if you need account or ticket load details.")

    # ── Agent output parsing ──────────────────────────────────────────────────
    @staticmethod
    def _parse_agent_output(agent_result: Any) -> tuple[str, list[str]]:
        messages = [m for m in (agent_result.get("messages", []) if isinstance(agent_result, dict) else [])
                    if isinstance(m, BaseMessage)]
        # Last AIMessage with content is the final draft
        draft = ""
        for msg in reversed(messages):
            if isinstance(msg, AIMessage):
                text = "\n".join(str(c) for c in msg.content) if isinstance(msg.content, list) else str(msg.content)
                if text.strip():
                    draft = text.strip()
                    break
        # Pull human-readable summaries out of tool responses
        tool_msgs = {m.tool_call_id: m for m in messages
                     if isinstance(m, ToolMessage) and m.tool_call_id}
        summaries: list[str] = []
        for msg in messages:
            if not isinstance(msg, AIMessage):
                continue
            for call in getattr(msg, "tool_calls", None) or []:
                resp = tool_msgs.get(str(call.get("id")))
                if not resp:
                    continue
                try:
                    parsed = json.loads(str(resp.content))
                    if isinstance(parsed, dict) and parsed.get("summary"):
                        summaries.append(parsed["summary"])
                except json.JSONDecodeError:
                    pass
        return draft, summaries

    # ── Fallbacks ─────────────────────────────────────────────────────────────
    def _llm_fallback(self, ticket: dict, customer: dict, tool_summaries: list[str]) -> str:
        tool_lines = "\n".join(f"- {s}" for s in tool_summaries if s) or "- none"
        try:
            response = self._llm.invoke([
                SystemMessage(content="You are a support copilot. Write only the final customer-facing reply."),
                HumanMessage(content=(
                    f"Customer: {customer.get('name')} ({customer['email']})\n"
                    f"Subject: {ticket['subject']}\n"
                    f"Description: {ticket['description']}\n\n"
                    f"Tool findings:\n{tool_lines}\n\n"
                    "Write a concise, empathetic reply with clear next steps."
                )),
            ])
            content = response.content
            return ("\n".join(str(c) for c in content) if isinstance(content, list) else str(content)).strip()
        except Exception:
            return ""

    @staticmethod
    def _template_fallback(ticket: dict, customer: dict, tool_summaries: list[str]) -> str:
        name   = customer.get("name") or customer.get("email") or "there"
        action = tool_summaries[0] if tool_summaries else "Our team is reviewing your case and will follow up shortly."
        return (f"Hi {name},\n\n"
                f"Thank you for contacting us about \"{ticket.get('subject', 'your issue')}\".\n\n"
                f"{action}\n\nBest regards,\nSupport Team")

