"""Builds the long-lived pipeline dependencies once per process."""

from __future__ import annotations

from .config import Settings
from .demo_cache import DemoCache
from .policy import get_policy
from .policy.validators import bin_vocabulary
from .providers.llm import build_text_llm
from .providers.vision import UnavailableVisionProvider
from .retrieval.corpus import load_manifest
from .retrieval.store import ChunkStore, HFEmbedder, Retriever
from .workflow import PipelineDeps


def build_deps(settings: Settings) -> tuple[PipelineDeps, ChunkStore]:
    policy = get_policy()
    store = ChunkStore(settings)
    if store.embed_model and store.embed_model != settings.embed_model:
        raise RuntimeError(
            f"Vector store was built with {store.embed_model}, but EMBED_MODEL is {settings.embed_model}. "
            "Run: python scripts/ingest.py"
        )
    manifest = load_manifest()
    embedder = HFEmbedder(settings.embed_model)
    embedder.embed_query("warm up")  # load the model now, not on the first request
    deps = PipelineDeps(
        settings=settings,
        policy=policy,
        retriever=Retriever(store, embedder),
        store=store.chunks,
        llm=build_text_llm(settings),
        vision=UnavailableVisionProvider(),
        demo_cache=DemoCache(settings.demo_cache_path),
        vocabulary=bin_vocabulary(policy, manifest.bin_vocabulary),
    )
    return deps, store
