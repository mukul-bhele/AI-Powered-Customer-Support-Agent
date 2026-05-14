from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException

from customer_support_agent.api.dependencies import get_settings_dep
from customer_support_agent.core.settings import Settings
from customer_support_agent.integrations.rag.chroma_kb import KnowledgeBaseService
from customer_support_agent.schemas.api import KnowledgeIngestRequest, KnowledgeIngestResponse


router = APIRouter()


@router.post("/api/knowledge/ingest", response_model=KnowledgeIngestResponse)
def ingest_knowledge_route(
    payload: KnowledgeIngestRequest,
    settings: Settings = Depends(get_settings_dep),
) -> dict[str, int]:
    try:
        return KnowledgeBaseService(settings=settings).ingest_directory(
            directory=settings.knowledge_base_path,
            clear_existing=payload.clear_existing,
        )
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Ingestion failed: {exc}") from exc
