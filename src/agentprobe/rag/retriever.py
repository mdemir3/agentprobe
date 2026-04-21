"""RAG retriever — finds relevant ground truth chunks for a given claim.

This is the "retrieval" in retrieval-augmented hallucination detection.
Given a claim like "Free shipping on orders over $50", it finds the
most relevant chunks from the target's ingested documents.
"""

from __future__ import annotations

import os
import re
from dataclasses import dataclass

import chromadb
from chromadb.config import Settings as ChromaSettings
from chromadb.utils import embedding_functions


@dataclass
class RetrievedChunk:
    """A chunk retrieved from the vector store."""

    text: str
    source_file: str
    relevance_score: float  # 1.0 = perfect match, 0.0 = irrelevant
    chunk_index: int


class GroundTruthRetriever:
    """Retrieves ground truth document chunks for hallucination checking."""

    def __init__(
        self,
        chroma_host: str = "localhost",
        chroma_port: int = 8100,
        chroma_path: str | None = None,
        embedding_model: str = "all-MiniLM-L6-v2",
    ):
        settings = ChromaSettings(anonymized_telemetry=False)
        use_http = os.environ.get("AGENTPROBE_CHROMA_USE_HTTP", "").lower() in (
            "1",
            "true",
            "yes",
        )
        # Default: on-disk Chroma (tests and local dev). Set AGENTPROBE_CHROMA_USE_HTTP=true
        # plus CHROMA_HOST/CHROMA_PORT in .env when using docker-compose Chroma server.
        if chroma_path:
            self.client = chromadb.PersistentClient(path=chroma_path, settings=settings)
        elif use_http:
            host = os.environ.get("CHROMA_HOST", chroma_host)
            port = int(os.environ.get("CHROMA_PORT", str(chroma_port)))
            self.client = chromadb.HttpClient(host=host, port=port, settings=settings)
        else:
            data_dir = os.environ.get("AGENTPROBE_CHROMA_DATA", ".chromadb")
            self.client = chromadb.PersistentClient(path=data_dir, settings=settings)

        self.embedding_fn = embedding_functions.SentenceTransformerEmbeddingFunction(
            model_name=embedding_model
        )

    def _collection_name(self, target_id: str) -> str:
        safe = re.sub(r"[^a-zA-Z0-9_-]", "_", target_id)[:50]
        return f"target_{safe}"

    def has_ground_truth(self, target_id: str) -> bool:
        """Check if a target has any ingested ground truth docs."""
        try:
            col = self.client.get_collection(
                name=self._collection_name(target_id),
                embedding_function=self.embedding_fn,
            )
            return col.count() > 0
        except Exception:
            return False

    def retrieve(
        self,
        target_id: str,
        query: str,
        top_k: int = 5,
    ) -> list[RetrievedChunk]:
        """Retrieve the top-k most relevant chunks for a query.

        Args:
            target_id: The target agent whose docs to search
            query: The claim or question to find evidence for
            top_k: How many chunks to return

        Returns:
            List of chunks sorted by relevance (most relevant first)
        """
        try:
            collection = self.client.get_collection(
                name=self._collection_name(target_id),
                embedding_function=self.embedding_fn,
            )
        except Exception:
            return []

        try:
            results = collection.query(
                query_texts=[query],
                n_results=top_k,
            )
        except Exception:
            return []

        chunks: list[RetrievedChunk] = []
        documents = results.get("documents", [[]])[0]
        metadatas = results.get("metadatas", [[]])[0]
        distances = results.get("distances", [[]])[0]

        for doc, meta, dist in zip(documents, metadatas, distances):
            # ChromaDB distance: lower = more similar. Convert to 0-1 score.
            # Typical cosine distance range is 0-2, so we invert and normalize.
            relevance = max(0.0, min(1.0, 1.0 - (dist / 2.0)))

            chunks.append(
                RetrievedChunk(
                    text=doc,
                    source_file=meta.get("source_file", "unknown") if meta else "unknown",
                    relevance_score=round(relevance, 3),
                    chunk_index=meta.get("chunk_index", 0) if meta else 0,
                )
            )

        return chunks

    def retrieve_multiple(
        self,
        target_id: str,
        queries: list[str],
        top_k_per_query: int = 3,
    ) -> list[RetrievedChunk]:
        """Retrieve chunks for multiple claims at once, deduplicated."""
        seen: set[str] = set()
        all_chunks: list[RetrievedChunk] = []

        for query in queries:
            chunks = self.retrieve(target_id, query, top_k=top_k_per_query)
            for chunk in chunks:
                key = chunk.text[:100]
                if key not in seen:
                    seen.add(key)
                    all_chunks.append(chunk)

        # Sort by relevance
        all_chunks.sort(key=lambda c: c.relevance_score, reverse=True)
        return all_chunks

    def count_chunks(self, target_id: str) -> int:
        """How many chunks are stored for this target."""
        try:
            collection = self.client.get_collection(
                name=self._collection_name(target_id),
                embedding_function=self.embedding_fn,
            )
            return collection.count()
        except Exception:
            return 0
