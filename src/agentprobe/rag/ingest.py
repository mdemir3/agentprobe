"""Document ingestion pipeline.

Takes user-provided documents (PDF, Markdown, text) and stores them as
embedded chunks in ChromaDB, tagged with a target_id. These documents
become the "ground truth" for hallucination detection.
"""

from __future__ import annotations

import hashlib
import os
import re
from dataclasses import dataclass
from pathlib import Path

import chromadb
from chromadb.config import Settings as ChromaSettings
from chromadb.utils import embedding_functions


# ─── Data models ─────────────────────────────────────────────────────────────


@dataclass
class IngestedChunk:
    """A single chunk of ingested content."""

    chunk_id: str
    text: str
    source_file: str
    chunk_index: int
    char_start: int
    char_end: int


@dataclass
class IngestionResult:
    """Summary of a document ingestion run."""

    target_id: str
    files_processed: int
    chunks_created: int
    total_characters: int
    collection_name: str
    errors: list[str]


# ─── Ingestor ────────────────────────────────────────────────────────────────


class DocumentIngestor:
    """Ingests documents into ChromaDB for a specific target agent.

    Each target gets its own ChromaDB collection. Documents are chunked
    with overlap to preserve context, then embedded and stored.
    """

    def __init__(
        self,
        chroma_host: str = "localhost",
        chroma_port: int = 8100,
        chroma_path: str | None = None,
        embedding_model: str = "all-MiniLM-L6-v2",
        chunk_size: int = 800,
        chunk_overlap: int = 150,
    ):
        self.chunk_size = chunk_size
        self.chunk_overlap = chunk_overlap

        settings = ChromaSettings(anonymized_telemetry=False)
        use_http = os.environ.get("AGENTPROBE_CHROMA_USE_HTTP", "").lower() in (
            "1",
            "true",
            "yes",
        )
        if chroma_path:
            self.client = chromadb.PersistentClient(path=chroma_path, settings=settings)
        elif use_http:
            host = os.environ.get("CHROMA_HOST", chroma_host)
            port = int(os.environ.get("CHROMA_PORT", str(chroma_port)))
            self.client = chromadb.HttpClient(host=host, port=port, settings=settings)
        else:
            data_dir = os.environ.get("AGENTPROBE_CHROMA_DATA", ".chromadb")
            self.client = chromadb.PersistentClient(path=data_dir, settings=settings)

        # Use local sentence-transformers embeddings (no API key needed)
        self.embedding_fn = embedding_functions.SentenceTransformerEmbeddingFunction(
            model_name=embedding_model
        )

    def _collection_name(self, target_id: str) -> str:
        """Generate a valid ChromaDB collection name for a target."""
        safe = re.sub(r"[^a-zA-Z0-9_-]", "_", target_id)[:50]
        return f"target_{safe}"

    def ingest_folder(
        self,
        target_id: str,
        folder_path: str,
        patterns: list[str] | None = None,
    ) -> IngestionResult:
        """Ingest all matching files in a folder."""
        patterns = patterns or ["*.pdf", "*.md", "*.txt"]
        folder = Path(folder_path)

        if not folder.exists():
            return IngestionResult(
                target_id=target_id,
                files_processed=0,
                chunks_created=0,
                total_characters=0,
                collection_name="",
                errors=[f"Folder not found: {folder_path}"],
            )

        files: list[Path] = []
        for pattern in patterns:
            files.extend(folder.rglob(pattern))

        return self.ingest_files(target_id, [str(f) for f in files])

    def ingest_files(self, target_id: str, file_paths: list[str]) -> IngestionResult:
        """Ingest a list of files for a target."""
        collection_name = self._collection_name(target_id)
        errors: list[str] = []

        # Get or create the collection (delete first to refresh ground truth)
        try:
            self.client.delete_collection(collection_name)
        except Exception:
            pass

        collection = self.client.create_collection(
            name=collection_name,
            embedding_function=self.embedding_fn,
            metadata={"target_id": target_id},
        )

        all_chunks: list[IngestedChunk] = []
        files_processed = 0

        for file_path in file_paths:
            try:
                text = self._read_file(file_path)
                if not text.strip():
                    errors.append(f"{file_path}: empty file")
                    continue

                chunks = self._chunk_text(text, file_path)
                all_chunks.extend(chunks)
                files_processed += 1

            except Exception as e:
                errors.append(f"{file_path}: {e}")

        # Batch insert into ChromaDB
        if all_chunks:
            collection.add(
                ids=[c.chunk_id for c in all_chunks],
                documents=[c.text for c in all_chunks],
                metadatas=[
                    {
                        "source_file": c.source_file,
                        "chunk_index": c.chunk_index,
                        "char_start": c.char_start,
                        "char_end": c.char_end,
                    }
                    for c in all_chunks
                ],
            )

        return IngestionResult(
            target_id=target_id,
            files_processed=files_processed,
            chunks_created=len(all_chunks),
            total_characters=sum(len(c.text) for c in all_chunks),
            collection_name=collection_name,
            errors=errors,
        )

    def _read_file(self, path: str) -> str:
        """Extract text from a file based on its extension."""
        suffix = Path(path).suffix.lower()

        if suffix == ".pdf":
            return self._read_pdf(path)
        elif suffix in (".md", ".txt", ".rst"):
            with open(path, encoding="utf-8") as f:
                return f.read()
        elif suffix == ".json":
            with open(path, encoding="utf-8") as f:
                return f.read()
        else:
            with open(path, encoding="utf-8", errors="ignore") as f:
                return f.read()

    def _read_pdf(self, path: str) -> str:
        """Extract text from a PDF."""
        try:
            from pypdf import PdfReader
        except ImportError:
            raise ImportError(
                "pypdf not installed. Install with: pip install pypdf"
            )

        reader = PdfReader(path)
        return "\n\n".join(page.extract_text() or "" for page in reader.pages)

    def _chunk_text(self, text: str, source_file: str) -> list[IngestedChunk]:
        """Split text into overlapping chunks with character positions tracked."""
        chunks: list[IngestedChunk] = []

        # Split by paragraphs first to avoid cutting mid-sentence when possible
        normalized = re.sub(r"\n{3,}", "\n\n", text.strip())

        position = 0
        chunk_index = 0
        text_len = len(normalized)

        while position < text_len:
            end = min(position + self.chunk_size, text_len)

            # If we're not at the end, try to break at a sentence boundary
            if end < text_len:
                # Look for sentence-ending punctuation in the last 200 chars
                window_start = max(position + self.chunk_size - 200, position)
                sentence_break = -1
                for i in range(end - 1, window_start, -1):
                    if normalized[i] in ".!?\n" and i + 1 < text_len and normalized[i + 1] in " \n":
                        sentence_break = i + 1
                        break
                if sentence_break > 0:
                    end = sentence_break

            chunk_text = normalized[position:end].strip()

            if not chunk_text:
                # Avoid stalling on whitespace-only slices (and bad end-overlap math).
                position = min(max(position + 1, end), text_len)
                continue

            chunk_id = hashlib.md5(
                f"{source_file}:{chunk_index}:{chunk_text[:50]}".encode()
            ).hexdigest()

            chunks.append(
                IngestedChunk(
                    chunk_id=chunk_id,
                    text=chunk_text,
                    source_file=os.path.basename(source_file),
                    chunk_index=chunk_index,
                    char_start=position,
                    char_end=end,
                )
            )
            chunk_index += 1

            # Move forward by chunk_size minus overlap
            position = end - self.chunk_overlap if end < text_len else end

        return chunks

    def list_targets(self) -> list[str]:
        """List all target IDs that have ingested documents."""
        collections = self.client.list_collections()
        return [c.metadata.get("target_id", c.name) for c in collections]

    def delete_target(self, target_id: str) -> bool:
        """Remove all documents for a target."""
        try:
            self.client.delete_collection(self._collection_name(target_id))
            return True
        except Exception:
            return False
