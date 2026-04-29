"""
Support Copilot — the core AI agent.

How a draft is generated:
  1. Search customer memory for past resolutions (Mem0)
  2. Search the knowledge base for relevant policy/FAQ chunks (ChromaDB)
  3. Build a prompt with that context and run the LangGraph agent (LLM + tools)
  4. If the agent returns empty text, call the LLM directly (no tools)
  5. If that also fails, return a plain template reply
"""
from __future__ import annotations

import json
import re
from typing import Any

from langchain.agents import create_agent
from langchain_core.messages import AIMessage, BaseMessage, HumanMessage, SystemMessage, ToolMessage
from langchain_groq import ChatGroq
from langgraph.checkpoint.memory import InMemorySaver

from customer_support_agent.core.settings import Settings
from customer_support_agent.integrations.memory.mem0_store import CustomerMemoryStore
from customer_support_agent.integrations.rag.chroma_kb import KnowledgeBaseService
from customer_support_agent.integrations.tools.support_tools import get_support_tools


class SupportCopilot:

    def __init__(self, settings: Settings):
        if not settings.groq_api_key:
            raise RuntimeError("GROQ_API_KEY is missing. Add it to .env before generating drafts.")

        self._settings = settings
        self._llm = ChatGroq(
            model=settings.groq_model,
            groq_api_key=settings.groq_api_key,
            temperature=settings.llm_temperature,
        )
        # LangGraph react agent — loops: think → call tool → think → write reply
        self._agent = create_agent(
            model=self._llm,
            tools=get_support_tools(),
            checkpointer=InMemorySaver(),   # keeps conversation history per ticket
            name="support_copilot_agent",
        )
        self.rag = KnowledgeBaseService(settings=settings)

        # Try to load memory; continue without it if an API key is missing
        self._memory_error: str | None = None
        try:
            self.memory = CustomerMemoryStore(settings=settings)
        except Exception as exc:
            self._memory_error = str(exc)

    # ─────────────────────────────────────────────────────────────────────────
    # Main entry point
    # ─────────────────────────────────────────────────────────────────────────

    def generate_draft(self, ticket: dict, customer: dict) -> dict:
        """
        Generate an AI draft reply for a ticket.
        Returns {"draft": str, "context_used": dict}.
        """
        query = f"{ticket['subject']}\n{ticket['description']}"

        # 1. Retrieve relevant past resolutions and KB chunks
        memory_hits = self._get_memories(query, customer)
        kb_hits     = self.rag.search(query=query, top_k=self._settings.rag_top_k)

        # 2. Run the agent with injected context
        system_msg = self._system_prompt(memory_hits, kb_hits)
        user_msg   = self._user_prompt(ticket, customer)
        thread_id  = f"ticket::{ticket.get('id', customer['email'])}"

        agent_output = self._agent.invoke(
            {"messages": [SystemMessage(content=system_msg), HumanMessage(content=user_msg)]},
            config={"configurable": {"thread_id": thread_id}, "recursion_limit": 40},
        )

        draft_text, tool_calls = self._parse_agent_output(agent_output)

        # 3. Fallback: call LLM directly if agent returned nothing
        used_fallback = False
        if not draft_text:
            draft_text    = self._llm_fallback(ticket, customer, memory_hits, kb_hits, tool_calls)
            used_fallback = True

        # 4. Last resort: plain template
        if not draft_text:
            draft_text    = self._template_fallback(ticket, customer, tool_calls)
            used_fallback = True

        # 5. Build the context/audit dict
        context = self._build_context(ticket, customer, memory_hits, kb_hits, tool_calls)
        if self._memory_error:
            context.setdefault("errors", []).append(f"Memory disabled: {self._memory_error}")
        if used_fallback:
            context.setdefault("errors", []).append("Agent returned empty reply; fallback was used.")
        context["agent_runtime"] = "langchain_create_agent"

        return {"draft": draft_text, "context_used": context}

    # ─────────────────────────────────────────────────────────────────────────
    # Memory — read
    # ─────────────────────────────────────────────────────────────────────────

    def _get_memories(self, query: str, customer: dict) -> list[dict]:
        """Search memory for this customer (and their company if set)."""
        if self._memory_error:
            return []

        email   = customer["email"].strip().lower()
        company = customer.get("company", "")
        hits    = self.memory.search(query=query, user_id=email, limit=self._settings.mem0_top_k)

        # Also search company-level memory if the customer has a company
        if company:
            company_id    = "company::" + re.sub(r"[^a-z0-9]+", "-", company.strip().lower()).strip("-")
            company_hits  = self.memory.search(query=query, user_id=company_id, limit=self._settings.mem0_top_k)
            hits          = hits + company_hits

        # Remove duplicates (keep first occurrence)
        seen: set[str] = set()
        deduped = []
        for h in hits:
            text = str(h.get("memory", "")).strip().lower()
            if text and text not in seen:
                seen.add(text)
                deduped.append(h)
        return deduped

    def list_customer_memories(self, customer_email: str, customer_company: str | None = None, limit: int = 20) -> list[dict]:
        """Return all stored memories for a customer."""
        hits = self.memory.list_memories(user_id=customer_email.strip().lower(), limit=limit)
        if customer_company:
            company_id   = "company::" + re.sub(r"[^a-z0-9]+", "-", customer_company.strip().lower()).strip("-")
            hits         = hits + self.memory.list_memories(user_id=company_id, limit=limit)
        # Deduplicate
        seen: set[str] = set()
        result = []
        for h in hits:
            text = str(h.get("memory", "")).strip().lower()
            if text and text not in seen:
                seen.add(text)
                result.append(h)
        return result[:limit]

    def search_customer_memories(self, customer_email: str, query: str, customer_company: str | None = None, limit: int = 10) -> list[dict]:
        """Semantic search within a customer's stored memories."""
        customer = {"email": customer_email, "company": customer_company}
        return self._get_memories(query, customer)[:limit]

    # ─────────────────────────────────────────────────────────────────────────
    # Memory — write
    # ─────────────────────────────────────────────────────────────────────────

    def save_accepted_resolution(
        self,
        customer_email: str,
        customer_company: str | None,
        ticket_subject: str,
        ticket_description: str,
        draft_content: str,
    ) -> None:
        """Save an accepted draft to memory so future tickets can benefit."""
        # Extract a few entity tags (plan, region, integration) to help future searches
        merged = f"{ticket_subject} {ticket_description} {draft_content}".lower()
        entity_links: list[str] = []

        for code in re.findall(r"\b([45]\d\d)\b", merged)[:4]:
            entity_links.append(f"http_status:{code}")
        for service in ["shopify", "stripe", "salesforce", "slack", "hubspot", "zendesk"]:
            if service in merged:
                entity_links.append(f"integration:{service}")

        # Save under individual scope
        self.memory.add_resolution(
            user_id=customer_email.strip().lower(),
            ticket_subject=ticket_subject,
            ticket_description=ticket_description,
            accepted_draft=draft_content,
            entity_links=entity_links,
        )
        # Save under company scope if available
        if customer_company:
            company_id = "company::" + re.sub(r"[^a-z0-9]+", "-", customer_company.strip().lower()).strip("-")
            self.memory.add_resolution(
                user_id=company_id,
                ticket_subject=ticket_subject,
                ticket_description=ticket_description,
                accepted_draft=draft_content,
                entity_links=entity_links,
            )

    # ─────────────────────────────────────────────────────────────────────────
    # Prompt builders
    # ─────────────────────────────────────────────────────────────────────────

    def _system_prompt(self, memory_hits: list[dict], kb_hits: list[dict]) -> str:
        memory_text = "\n".join(f"- {h.get('memory', '')}" for h in memory_hits) or "- None"
        kb_text     = "\n".join(f"- [{h.get('source')}] {h.get('content', '')}" for h in kb_hits) or "- None"
        return (
            "You are an AI copilot for customer support agents.\n"
            "Write concise, empathetic, and actionable draft replies.\n"
            "Call tools to check plan/billing info when needed.\n\n"
            f"Customer past resolutions:\n{memory_text}\n\n"
            f"Relevant knowledge base:\n{kb_text}\n\n"
            "Rules: start with empathy, give clear next steps, stay under 180 words."
        )

    @staticmethod
    def _user_prompt(ticket: dict, customer: dict) -> str:
        return (
            f"Customer: {customer.get('name') or 'Unknown'} ({customer['email']})\n"
            f"Company:  {customer.get('company') or 'Unknown'}\n"
            f"Subject:  {ticket['subject']}\n"
            f"Priority: {ticket.get('priority', 'medium')}\n\n"
            f"{ticket['description']}\n\n"
            "Write a draft reply. Use tools if you need account/plan details."
        )

    # ─────────────────────────────────────────────────────────────────────────
    # Agent output parsing
    # ─────────────────────────────────────────────────────────────────────────

    def _parse_agent_output(self, agent_result: Any) -> tuple[str, list[dict]]:
        """
        Extract the final draft text and a list of tool call records
        from the agent's raw message list.
        """
        messages = agent_result.get("messages", []) if isinstance(agent_result, dict) else []
        messages = [m for m in messages if isinstance(m, BaseMessage)]

        # The last AIMessage with content is the draft
        draft_text = ""
        for msg in reversed(messages):
            if isinstance(msg, AIMessage):
                content = msg.content
                text    = "\n".join(str(c) for c in content) if isinstance(content, list) else str(content)
                if text.strip():
                    draft_text = text.strip()
                    break

        # Build a lookup: tool_call_id → ToolMessage
        tool_responses = {
            m.tool_call_id: m
            for m in messages
            if isinstance(m, ToolMessage) and m.tool_call_id
        }

        # Collect one trace entry per tool call
        tool_calls: list[dict] = []
        for msg in messages:
            if not isinstance(msg, AIMessage):
                continue
            for call in getattr(msg, "tool_calls", None) or []:
                tool_name = call.get("name", "unknown_tool")
                tool_id   = call.get("id")
                response  = tool_responses.get(str(tool_id)) if tool_id else None

                if response is None:
                    tool_calls.append({
                        "tool_name":    tool_name,
                        "tool_call_id": tool_id,
                        "arguments":    call.get("args") or {},
                        "status":       "skipped",
                        "summary":      f"Tool '{tool_name}' was called but returned no result.",
                        "output":       None,
                        "output_text":  "",
                    })
                else:
                    raw_text = str(response.content)
                    # Try to parse JSON for a nicer summary
                    try:
                        parsed  = json.loads(raw_text)
                        summary = parsed.get("summary", raw_text) if isinstance(parsed, dict) else raw_text
                        output  = parsed if isinstance(parsed, dict) else None
                    except json.JSONDecodeError:
                        parsed, summary, output = None, raw_text, None

                    tool_calls.append({
                        "tool_name":    tool_name,
                        "tool_call_id": tool_id,
                        "arguments":    call.get("args") or {},
                        "status":       "error" if getattr(response, "status", None) == "error" else "ok",
                        "summary":      summary,
                        "output":       output,
                        "output_text":  raw_text,
                    })

        return draft_text, tool_calls

    # ─────────────────────────────────────────────────────────────────────────
    # Fallbacks
    # ─────────────────────────────────────────────────────────────────────────

    def _llm_fallback(self, ticket: dict, customer: dict, memory_hits: list[dict], kb_hits: list[dict], tool_calls: list[dict]) -> str:
        """Call the LLM directly (no tools) when the agent returned empty text."""
        memory_lines = [h.get("memory", "") for h in memory_hits[:3]]
        kb_lines     = [f"[{h.get('source')}] {h.get('content', '')}" for h in kb_hits[:3]]
        tool_lines   = [tc.get("summary", "") for tc in tool_calls if tc.get("summary")]

        def bullets(lines: list[str]) -> str:
            return "\n".join(f"- {l}" for l in lines if l) or "- none"

        try:
            response = self._llm.invoke([
                SystemMessage(content="You are a support copilot. Write only the final customer-facing reply."),
                HumanMessage(content=(
                    f"Customer: {customer.get('name')} ({customer['email']})\n"
                    f"Subject: {ticket['subject']}\n"
                    f"Description: {ticket['description']}\n\n"
                    f"Memory:\n{bullets(memory_lines)}\n\n"
                    f"Knowledge:\n{bullets(kb_lines)}\n\n"
                    f"Tool findings:\n{bullets(tool_lines)}\n\n"
                    "Write a concise, empathetic reply with clear next steps."
                )),
            ])
            content = response.content
            return ("\n".join(str(c) for c in content) if isinstance(content, list) else str(content)).strip()
        except Exception:
            return ""

    @staticmethod
    def _template_fallback(ticket: dict, customer: dict, tool_calls: list[dict]) -> str:
        """Return a safe static reply when all AI generation fails."""
        name        = customer.get("name") or customer.get("email") or "there"
        action_line = next((tc["summary"] for tc in tool_calls if tc.get("summary")), "")
        return (
            f"Hi {name},\n\n"
            f"Thank you for contacting us about \"{ticket.get('subject', 'your issue')}\".\n\n"
            f"{action_line or 'Our team is reviewing your case and will follow up shortly.'}\n\n"
            "Best regards,\nSupport Team"
        )

    # ─────────────────────────────────────────────────────────────────────────
    # Context / audit dict
    # ─────────────────────────────────────────────────────────────────────────

    def _build_context(self, ticket: dict, customer: dict, memory_hits: list[dict], kb_hits: list[dict], tool_calls: list[dict]) -> dict:
        """Build the structured context dict stored alongside the draft for auditability."""
        kb_sources  = list(dict.fromkeys(h.get("source", "") for h in kb_hits if h.get("source")))
        tool_errors = [tc for tc in tool_calls if tc.get("status") != "ok"]

        def trim(text: Any, limit: int = 180) -> str:
            s = str(text or "").strip()
            return s if len(s) <= limit else s[:limit - 3] + "..."

        return {
            "version":  2,
            "ticket":   {"id": ticket.get("id"), "subject": ticket.get("subject"), "priority": ticket.get("priority")},
            "customer": {"id": customer.get("id"), "email": customer.get("email"), "name": customer.get("name")},
            "signals": {
                "memory_hit_count":    len(memory_hits),
                "knowledge_hit_count": len(kb_hits),
                "tool_call_count":     len(tool_calls),
                "tool_error_count":    len(tool_errors),
                "knowledge_sources":   kb_sources,
            },
            "highlights": {
                "memory":    [trim(h.get("memory"))    for h in memory_hits[:3]],
                "knowledge": [trim(f"[{h.get('source')}] {h.get('content')}") for h in kb_hits[:3]],
                "tools":     [trim(tc.get("summary"))  for tc in tool_calls[:3]],
            },
            "memory_hits":    memory_hits,
            "knowledge_hits": kb_hits,
            "tool_calls":     tool_calls,
        }
