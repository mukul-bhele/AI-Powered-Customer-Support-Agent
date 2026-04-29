"""
Knowledge service — thin orchestration layer over KnowledgeBaseService.

The router calls this service; the service delegates to the RAG integration.
Keeping this indirection means routers stay unaware of ChromaDB internals.
"""
from __future__ import annotations

from customer_support_agent.core.settings import Settings
from customer_support_agent.integrations.rag.chroma_kb import KnowledgeBaseService


class KnowledgeService:

    def __init__(self, settings: Settings):
        self._settings = settings

    def ingest(self, clear_existing: bool = False) -> dict[str, int]:
        """
        Index all .md/.txt files from the knowledge_base/ directory.

        Args:
            clear_existing: Wipe the ChromaDB collection first if True.

        Returns:
            {"files_indexed": int, "chunks_indexed": int, "collection_count": int}
        """
        rag = KnowledgeBaseService(settings=self._settings)
        return rag.ingest_directory(
            directory=self._settings.knowledge_base_path,
            clear_existing=clear_existing,
        )
