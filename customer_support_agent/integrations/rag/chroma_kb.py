"""
Knowledge Base — ChromaDB vector store wrapper.
Responsibilities:
  - ingest_directory()  → reads .md/.txt files, splits them into chunks,
                          and upserts them into a ChromaDB collection
  - search()            → semantic similarity search over those chunks
Embedding providers (picked automatically from settings, in priority order):
   OpenAI         (OPENAI_API_KEY)   ← uses text-embedding-3-small
"""
from __future__ import annotations
import hashlib
import os
from pathlib import Path
from typing import Any
import chromadb
from chromadb.utils import embedding_functions
from langchain_text_splitters import RecursiveCharacterTextSplitter
from customer_support_agent.core.settings import Settings
class KnowledgeBaseService:
    def __init__(self, settings: Settings):
        self._settings = settings

        # Persistent ChromaDB client — data survives server restarts
        self._client = chromadb.PersistentClient(path=str(settings.chroma_rag_path))

        # Each embedding model produces vectors in a different space,
        # so we use a separate ChromaDB collection per provider.
        # Mixing embeddings from different models in one collection breaks search.
        self._collection_name = "support_kb_openai"
        self._embedding_function = self._build_embedding_function()

        # get_or_create → safe to call on every startup
        self._collection = self._client.get_or_create_collection(
            name=self._collection_name,
            embedding_function=self._embedding_function,
        )

        # Text splitter: breaks large documents into overlapping chunks
        # so context is not lost at chunk boundaries
        self._splitter = RecursiveCharacterTextSplitter(
            chunk_size=settings.rag_chunk_size,
            chunk_overlap=settings.rag_chunk_overlap,
        )

    def _build_embedding_function(self) -> Any:
        """
        Return the embedding function based on available API keys.
        Priority:
          OpenAI         — if OPENAI_API_KEY is set (text-embedding-3-small)
        """
        if self._settings.openai_api_key:
            # OpenAI's text-embedding-3-small is fast, cheap, and high quality
            return embedding_functions.OpenAIEmbeddingFunction(
                api_key=self._settings.openai_api_key,
                model_name="text-embedding-3-small",
            )

    def ingest_directory(self, directory: Path, clear_existing: bool = False) -> dict[str, int]:
        """
        Read all .md and .txt files in `directory`, chunk them, and store in ChromaDB.
        Args:
            directory:      Path to the knowledge_base/ folder.
            clear_existing: If True, wipe the collection before ingesting.
                            Useful when documents have been deleted or renamed.
        Returns:
            Dict with files_indexed, chunks_indexed, and collection_count.
        """
        if clear_existing:
            self._client.delete_collection(name=self._collection_name)
            self._collection = self._client.get_or_create_collection(
                name=self._collection_name,
                embedding_function=self._embedding_function,
            )

        source_files = sorted([*directory.glob("*.md"), *directory.glob("*.txt")])
        docs:      list[str]            = []
        ids:       list[str]            = []
        metadatas: list[dict[str, Any]] = []

        for file_path in source_files:
            text   = file_path.read_text(encoding="utf-8")
            chunks = self._splitter.split_text(text)

            for index, chunk in enumerate(chunks):
                # Include a content hash in the ID so re-ingesting the same
                # content never creates duplicate entries (upsert is idempotent)
                chunk_hash = hashlib.sha1(chunk.encode("utf-8")).hexdigest()[:10]
                doc_id     = f"{file_path.stem}-{index}-{chunk_hash}"

                docs.append(chunk)
                ids.append(doc_id)
                metadatas.append({"source": file_path.name, "chunk_index": index})

        if docs:
            # upsert = insert-or-update; safe to call multiple times
            self._collection.upsert(documents=docs, ids=ids, metadatas=metadatas)
        return {
            "files_indexed": len(source_files),
            "chunks_indexed": len(docs),
            "collection_count": self._collection.count(),
        }
   
    def search(self, query: str, top_k: int | None = None) -> list[dict[str, Any]]:        
        """
        Find the most relevant knowledge base chunks for a query string.
        Returns an empty list if the collection has not been ingested yet.
        Each result contains:
          - content:  the chunk text
          - source:   the originating file name
          - distance: lower = more similar
        """
        if self._collection.count() == 0:
            return []

        results = self._collection.query(
            query_texts=[query],
            n_results=top_k or self._settings.rag_top_k,
            include=["documents", "metadatas", "distances"],
        )
        # ChromaDB returns nested lists (one per query text); we only send one
        documents = (results.get("documents") or [[]])[0]
        metadatas = (results.get("metadatas") or [[]])[0]
        distances = (results.get("distances") or [[]])[0]
        return [
            {
                "content":  documents[i],
                "source":   metadatas[i].get("source", "unknown") if i < len(metadatas) else "unknown",
                "distance": distances[i] if i < len(distances) else None,
            }
            for i in range(len(documents))
        ]
