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


# Pinned model revisions (the official BAAI repo ships onnx/model.onnx), so a
# rebuild always embeds with the same weights.
MODEL_REVISIONS = {"BAAI/bge-small-en-v1.5": "5c38ec7c405ec4b44b94cc5a9bb96e735b38267a"}
# Query instruction bge English models were trained with (the same one
# LlamaIndex's HuggingFaceEmbedding adds); documents get none.
QUERY_INSTRUCTIONS = {"BAAI/bge-small-en-v1.5": "Represent this question for searching relevant passages: "}


class OnnxEmbedder:
    """Local bge-small embeddings on ONNX Runtime (loaded lazily).

    Same weights and maths as sentence-transformers (CLS pooling, max 512
    tokens, L2-normalised) without torch, so the app fits a 512 MB host.
    """

    max_length = 512
    batch_size = 32

    def __init__(self, model_name: str) -> None:
        self.model_name = model_name
        self.revision = MODEL_REVISIONS.get(model_name)
        self.query_instruction = QUERY_INSTRUCTIONS.get(model_name, "")

    @cached_property
    def _session(self) -> Any:
        import onnxruntime as ort
        from huggingface_hub import hf_hub_download

        path = hf_hub_download(self.model_name, "onnx/model.onnx", revision=self.revision)
        opts = ort.SessionOptions()
        opts.intra_op_num_threads = 1  # one query at a time; keeps memory and CPU low
        return ort.InferenceSession(path, sess_options=opts, providers=["CPUExecutionProvider"])

    @cached_property
    def _tokenizer(self) -> Any:
        from huggingface_hub import hf_hub_download
        from tokenizers import Tokenizer

        tok = Tokenizer.from_file(hf_hub_download(self.model_name, "tokenizer.json", revision=self.revision))
        tok.enable_truncation(max_length=self.max_length)
        tok.enable_padding()
        return tok

    def _embed(self, texts: list[str]) -> list[list[float]]:
        import numpy as np

        out: list[list[float]] = []
        input_names = {i.name for i in self._session.get_inputs()}
        for start in range(0, len(texts), self.batch_size):
            enc = self._tokenizer.encode_batch(texts[start : start + self.batch_size])
            feed = {
                "input_ids": np.array([e.ids for e in enc], dtype=np.int64),
                "attention_mask": np.array([e.attention_mask for e in enc], dtype=np.int64),
                "token_type_ids": np.array([e.type_ids for e in enc], dtype=np.int64),
            }
            hidden = self._session.run(None, {k: v for k, v in feed.items() if k in input_names})[0]
            cls = hidden[:, 0]
            cls = cls / np.linalg.norm(cls, axis=1, keepdims=True)
            out.extend(cls.astype(float).tolist())
        return out

    def embed_query(self, text: str) -> list[float]:
        return self._embed([self.query_instruction + text])[0]

    def embed_documents(self, texts: list[str]) -> list[list[float]]:
        return self._embed(texts)


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
        # Chroma returns records in insertion order, i.e. the ingest order.
        self.order: dict[str, int] = {cid: i for i, cid in enumerate(records["ids"])}

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
        scored = [
            ScoredChunk(chunk=self.store.chunks[cid], score=round(1.0 - float(d), 4))
            for cid, d in zip(ids, distances, strict=True)
            if cid in self.store.chunks
        ]
        # Some rules appear verbatim in several sources and tie exactly; break
        # ties by corpus (manifest) order so the cited source does not depend
        # on float noise.
        return sorted(scored, key=lambda sc: (-sc.score, self.store.order[sc.chunk.chunk_id]))
