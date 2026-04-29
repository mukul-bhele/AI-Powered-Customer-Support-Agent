"""
API data contracts (Pydantic models).

Every model here defines what data is accepted (request) or returned
(response) by a FastAPI endpoint. Pydantic validates all fields
automatically — wrong types or missing required fields return HTTP 422
before any business logic runs.

Model groups:
  1. Ticket models         — creating and viewing support tickets
  2. Draft models          — AI-generated reply drafts (nested structure)
  3. Knowledge base models — ingesting markdown docs into the vector store
  4. Customer memory models — querying per-customer AI memory
"""
from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, EmailStr, Field


# ── 1. Ticket models ──────────────────────────────────────────────────────────

class TicketCreateRequest(BaseModel):
    """Body sent by the client when submitting a new support ticket."""
    customer_email:   EmailStr                               # validated email format
    customer_name:    str | None = None
    customer_company: str | None = None
    subject:          str = Field(min_length=3)              # at least 3 characters
    description:      str = Field(min_length=10)             # at least 10 characters
    priority:         Literal["low", "medium", "high", "urgent"] = "medium"
    auto_generate:    bool = True                            # trigger AI draft immediately


class TicketResponse(BaseModel):
    """Full ticket object returned by the API."""
    id:               int
    customer_id:      int
    customer_email:   EmailStr
    customer_name:    str | None = None
    customer_company: str | None = None
    subject:          str
    description:      str
    status:           str
    priority:         str
    created_at:       str
    updated_at:       str


# ── 2. Draft models ───────────────────────────────────────────────────────────
# Drafts have a nested structure so agents can see *how* the AI built the reply.
# Hierarchy:
#   DraftResponse
#     └── context_used: StructuredDraftContext
#           ├── signals:    DraftSignals    (counts of memory/KB/tool hits)
#           ├── highlights: DraftHighlights (top snippets from each source)
#           └── tool_calls: list[DraftToolCall]

class DraftSignals(BaseModel):
    """Counters summarising what the AI used when writing the draft."""
    memory_hit_count:    int = 0             # customer memories retrieved
    knowledge_hit_count: int = 0             # KB chunks retrieved
    tool_call_count:     int = 0             # external tools invoked
    tool_error_count:    int = 0             # tools that returned an error
    knowledge_sources:   list[str] = Field(default_factory=list)  # source file names


class DraftHighlights(BaseModel):
    """Top 3 text snippets from each source that most influenced the draft."""
    memory:    list[str] = Field(default_factory=list)
    knowledge: list[str] = Field(default_factory=list)
    tools:     list[str] = Field(default_factory=list)


class DraftToolCall(BaseModel):
    """Record of a single tool invocation made by the AI agent."""
    tool_name:    str
    tool_call_id: str | None = None
    arguments:    dict[str, Any] = Field(default_factory=dict)
    status:       str                         # "ok" | "error" | "skipped"
    summary:      str | None = None           # human-readable one-liner
    output:       dict[str, Any] | None = None
    output_text:  str                         # raw tool response text


class StructuredDraftContext(BaseModel):
    """
    Full explanation of how the AI generated a draft.

    Stored as JSON in drafts.context_used and returned in every
    DraftResponse so agents can audit the AI reasoning.
    """
    version:        int = 2
    ticket:         dict[str, Any] | None = None    # ticket snapshot at draft time
    customer:       dict[str, Any] | None = None    # customer snapshot at draft time
    signals:        DraftSignals | dict[str, Any] | None = None
    highlights:     DraftHighlights | dict[str, Any] | None = None
    memory_hits:    list[dict[str, Any]] = Field(default_factory=list)
    knowledge_hits: list[dict[str, Any]] = Field(default_factory=list)
    tool_calls:     list[DraftToolCall | dict[str, Any]] = Field(default_factory=list)
    errors:         list[str] = Field(default_factory=list)


class DraftResponse(BaseModel):
    """Full draft object returned by the API."""
    id:           int
    ticket_id:    int
    content:      str                                        # the actual reply text
    context_used: StructuredDraftContext | dict[str, Any] | None = None
    status:       str                                        # pending | accepted | discarded
    created_at:   str


class DraftUpdateRequest(BaseModel):
    """Body sent when an agent edits, accepts, or discards a draft."""
    content: str | None = None
    status:  Literal["pending", "accepted", "discarded"] | None = None


class GenerateDraftResponse(BaseModel):
    """Returned by POST /api/tickets/{id}/generate-draft."""
    ticket_id: int
    draft:     DraftResponse


# ── 3. Knowledge base models ──────────────────────────────────────────────────

class KnowledgeIngestRequest(BaseModel):
    """Body sent when triggering a knowledge base re-index."""
    clear_existing: bool = False   # if True, wipes ChromaDB before re-ingesting


class KnowledgeIngestResponse(BaseModel):
    """Stats returned after a successful ingest."""
    files_indexed:    int
    chunks_indexed:   int
    collection_count: int


# ── 4. Customer memory models ─────────────────────────────────────────────────

class CustomerMemoriesResponse(BaseModel):
    """All stored memories for a customer (GET /customers/{id}/memories)."""
    customer_id:    int
    customer_email: EmailStr
    memories:       list[dict[str, Any]]


class CustomerMemorySearchResponse(BaseModel):
    """Semantic search results within a customer's memories."""
    customer_id:    int
    customer_email: EmailStr
    query:          str
    results:        list[dict[str, Any]]
