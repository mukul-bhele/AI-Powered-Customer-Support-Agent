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
    customer_email: EmailStr                               # validated email format
    customer_name:  str | None = None
    subject:        str = Field(min_length=3)              # at least 3 characters
    description:    str = Field(min_length=10)             # at least 10 characters
    priority:       Literal["low", "medium", "high", "urgent"] = "medium"
    auto_generate:  bool = True                            # trigger AI draft immediately


class TicketResponse(BaseModel):
    """Full ticket object returned by the API."""
    id:             int
    customer_id:    int
    customer_email: EmailStr
    customer_name:  str | None = None
    subject:        str
    description:    str
    status:         str
    priority:       str
    created_at:     str
    updated_at:     str


# ── 2. Draft models ───────────────────────────────────────────────────────────

class DraftResponse(BaseModel):
    """Full draft object returned by the API."""
    id:         int
    ticket_id:  int
    content:    str                                        # the actual reply text
    status:     str                                        # pending | accepted | discarded
    created_at: str

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
