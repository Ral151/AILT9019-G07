"""Read-only access to the persisted Chroma store, plus vector search."""

from __future__ import annotations

from collections.abc import Mapping
from functools import cached_property
from typing import Any, Protocol

from ..config import Settings
from ..schemas import Chunk, ScoredChunk
from .corpus import chunk_from_record
from .query import normalise_query


class Embedder(Protocol):
    def embed_query(self, text: str) -> list[float]: ...


class HFEmbedder:
    """Local bge-small embeddings through LlamaIndex (loaded lazily)."""

    def __init__(self, model_name: str) -> None:
        self.model_name = model_name

    @cached_property
    def _model(self) -> Any:
        from llama_index.embeddings.huggingface import HuggingFaceEmbedding

        # bge models get their query instruction from LlamaIndex automatically.
        return HuggingFaceEmbedding(model_name=self.model_name, normalize=True)

    def embed_query(self, text: str) -> list[float]:
        return list(self._model.get_query_embedding(text))

    def embed_documents(self, texts: list[str]) -> list[list[float]]:
        return [list(v) for v in self._model.get_text_embedding_batch(texts)]


class StoreNotBuiltError(RuntimeError):
    pass


class ChunkStore:
    """All chunks from Chroma, loaded once. Excerpts are copied from here."""

    def __init__(self, settings: Settings) -> None:
        import chromadb

        if not settings.chroma_path.exists():
            raise StoreNotBuiltError(
                f"No vector store at {settings.chroma_path}. Run: python scripts/ingest.py"
            )
        client = chromadb.PersistentClient(path=str(settings.chroma_path))
        try:
            self.collection = client.get_collection(settings.chroma_collection)
        except Exception as exc:  # chromadb raises different types across versions
            raise StoreNotBuiltError(
                f"Collection {settings.chroma_collection!r} missing. Run: python scripts/ingest.py"
            ) from exc
        meta = self.collection.metadata or {}
        self.corpus_version = str(meta.get("corpus_version", "unknown"))
        self.embed_model = str(meta.get("embed_model", ""))
        records = self.collection.get(include=["documents", "metadatas"])
        self.chunks: dict[str, Chunk] = {
            cid: chunk_from_record(cid, doc, md)
            for cid, doc, md in zip(records["ids"], records["documents"], records["metadatas"], strict=True)
        }

    def streams(self) -> list[str]:
        return sorted({c.stream for c in self.chunks.values() if c.stream})


class Retriever:
    def __init__(self, store: ChunkStore, embedder: Embedder) -> None:
        self.store = store
        self.embedder = embedder

    def search(self, query: str, k: int, where: Mapping[str, Any] | None = None) -> list[ScoredChunk]:
        vector = self.embedder.embed_query(normalise_query(query))
        result = self.store.collection.query(
            query_embeddings=[vector],
            n_results=k,
            where=dict(where) if where else None,
            include=["distances"],
        )
        ids = result["ids"][0]
        distances = result["distances"][0] if result["distances"] else [1.0] * len(ids)
        # Collection uses cosine distance, so similarity = 1 - distance.
        return [
            ScoredChunk(chunk=self.store.chunks[cid], score=round(1.0 - float(d), 4))
            for cid, d in zip(ids, distances, strict=True)
            if cid in self.store.chunks
        ]
