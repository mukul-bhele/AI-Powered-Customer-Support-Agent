"""
Customer memory store — Mem0 wrapper.

Stores past ticket resolutions per customer so the AI can personalise
future replies. Supports three embedding providers (pick one in .env):
  - OpenAI          → set OPENAI_API_KEY
"""
from __future__ import annotations
from typing import Any  # used in _to_list signature
from customer_support_agent.core.settings import Settings

try:
    from mem0 import Memory
except ImportError:
    Memory = None


class CustomerMemoryStore:
    def __init__(self, settings: Settings):
        if Memory is None:
            raise RuntimeError("mem0ai is not installed. Run: pip install mem0ai")

        config: dict[str, Any] = {
            "llm": {
                "provider": "groq",
                "config": {
                    "model":       settings.groq_model,
                    "api_key":     settings.groq_api_key,
                    "temperature": settings.llm_temperature,
                },
            },
            "vector_store": {
                "provider": "chroma",
                "config": {"path": str(settings.chroma_mem0_path)},
            },
        }

        # Add whichever embedder is configured
        if settings.openai_api_key:
            config["embedder"] = {
                "provider": "openai",
                "config": {"api_key": settings.openai_api_key},
            }
        else:
            raise RuntimeError(
                "No embedding provider configured for Mem0. "
                "Set OPENAI_API_KEY"
            )

        self._memory = Memory.from_config(config)

    # ── Read ──────────────────────────────────────────────────────────────────
    def search(self, query: str, user_id: str, limit: int = 5) -> list[dict]:
        """Return the memories most relevant to `query` for this user."""
        try:
            raw = self._memory.search(query, user_id=user_id, limit=limit)
        except TypeError:
            raw = self._memory.search(query, user_id=user_id)  # older mem0 without limit
        return self._to_list(raw, limit)

    def list_memories(self, user_id: str, limit: int = 20) -> list[dict]:
        """Return all stored memories for a user."""
        if not hasattr(self._memory, "get_all"):
            return []  # older mem0 versions don't support get_all
        return self._to_list(self._memory.get_all(user_id=user_id), limit)

    # ── Write ─────────────────────────────────────────────────────────────────
    def add_resolution(
        self,
        user_id: str,
        ticket_subject: str,
        ticket_description: str,
        accepted_draft: str,
        entity_links: list[str] | None = None,
    ) -> None:
        """Save an accepted ticket resolution as a user/assistant memory pair."""
        extra = "\nLinked entities: " + ", ".join(entity_links) if entity_links else ""
        messages = [
            {"role": "user",      "content": f"Ticket: {ticket_subject}\nProblem: {ticket_description}"},
            {"role": "assistant", "content": f"Resolution:\n{accepted_draft}{extra}"},
        ]
        self._add(messages, user_id=user_id, metadata={"type": "resolution"})

    def add_interaction(self, user_id: str, user_input: str, assistant_response: str, metadata: dict | None = None) -> None:
        """Save a generic user/assistant exchange to memory."""
        messages = [
            {"role": "user",      "content": user_input},
            {"role": "assistant", "content": assistant_response},
        ]
        self._add(messages, user_id=user_id, metadata=metadata)

    # ── Private helpers ───────────────────────────────────────────────────────

    def _add(self, messages: list[dict], user_id: str, metadata: dict | None = None) -> None:
        try:
            self._memory.add(messages, user_id=user_id, metadata=metadata or {})
        except TypeError:
            self._memory.add(messages, user_id=user_id)  # older mem0 without metadata

    def _to_list(self, raw: Any, limit: int) -> list[dict]:
        """
        Normalise Mem0's varying response shapes into a plain list of dicts.
        Each item: {"memory": str, "score": float|None, "metadata": dict}
        """
        # Unwrap {"results": [...]} wrapper used by newer mem0 versions
        if isinstance(raw, dict):
            raw = raw.get("results") or []
        if not isinstance(raw, list):
            return []

        result = []
        for entry in raw[:limit]:
            if isinstance(entry, dict):
                text = entry.get("memory") or entry.get("content") or ""
                if text:
                    result.append({"memory": text, "score": entry.get("score"), "metadata": entry.get("metadata") or {}})
            elif entry:
                result.append({"memory": str(entry), "score": None, "metadata": {}})
        return result
