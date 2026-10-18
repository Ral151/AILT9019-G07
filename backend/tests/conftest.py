from __future__ import annotations

from collections.abc import Mapping
from pathlib import Path
from typing import Any

import pytest

from backend.app.config import load_settings
from backend.app.demo_cache import DemoCache
from backend.app.policy import Policy, get_policy
from backend.app.providers.llm import LLMResult, MockTextLLM, ProviderError
from backend.app.providers.vision import UnavailableVisionProvider
from backend.app.schemas import Chunk, ScoredChunk
from backend.app.workflow import Pipeline, PipelineDeps


def make_chunk(
    chunk_id: str,
    text: str,
    *,
    tier: str = "general_recyclable",
    stream: str | None = None,
    section: str = "Test > DOs",
    caveats: tuple[str, ...] = (),
    applies_to: tuple[str, ...] = (),
    line: int = 1,
) -> Chunk:
    return Chunk(
        chunk_id=chunk_id,
        source_id="test_source",
        doc_title="Test document",
        url="https://example.org/doc",
        retrieved_at="2026-10-18",
        section=section,
        line_start=line,
        line_end=line,
        rule_tier=tier,  # type: ignore[arg-type]
        stream=stream,
        caveat_tags=caveats,
        applies_to=applies_to,
        text=text,
    )


# A small corpus shaped like the real one.
CHUNKS = [
    make_chunk("plastic-do", "Beverage plastic bottles", stream="Plastic", section="Plastic > DOs", line=1),
    make_chunk("metal-do", "Aluminium cans and iron cans", stream="Metal", section="Metal > DOs", line=2),
    make_chunk("metal-dont", "Aerosol cans", tier="info", section="Metal > DON'Ts", caveats=("listed_as_dont",), line=3),
    make_chunk(
        "smart-glass",
        "Glass bottle (only at Central Podium Levels and Pine Court)",
        stream="Glass Bottle",
        section="Smart Recycling Bins",
        caveats=("smart_point_accepted_list",),
        line=4,
    ),
    make_chunk(
        "battery-do",
        "All types of portable rechargeable batteries from households",
        tier="hazardous_unified",
        stream="Rechargeable Battery",
        section="Rechargeable Battery > DOs",
        applies_to=("battery", "batteries", "rechargeable", "power bank"),
        line=5,
    ),
    make_chunk(
        "battery-dont",
        "Single use batteries",
        tier="hazardous_unified",
        section="Rechargeable Battery > DON'Ts",
        applies_to=("battery", "batteries", "single use", "AA"),
        line=6,
    ),
]
STORE = {c.chunk_id: c for c in CHUNKS}


class FakeRetriever:
    """Returns preset scores per query keyword; ignores embeddings."""

    def __init__(self, scores: dict[str, float] | None = None, default: float = 0.5) -> None:
        self.scores = scores or {}
        self.default = default

    def search(self, query: str, k: int, where: Mapping[str, Any] | None = None) -> list[ScoredChunk]:
        q = query.lower()
        out = []
        for c in CHUNKS:
            if where and c.rule_tier != where.get("rule_tier"):
                continue
            words = {w for w in c.text.lower().replace("(", " ").split()}
            score = self.default + (0.3 if any(w.rstrip("s") in q for w in words if len(w) > 3) else 0.0)
            score = self.scores.get(c.chunk_id, score)
            out.append(ScoredChunk(chunk=c, score=score))
        return sorted(out, key=lambda s: s.score, reverse=True)[:k]


class ScriptedLLM:
    """Returns queued outputs per task; raises ProviderError when told to."""

    name = "scripted"

    def __init__(self, answers: list[Any], intent: dict[str, Any] | None = None) -> None:
        self.answers = list(answers)
        self.intent = intent or {"intent": "recycling_question", "items": [], "mentions_location_outside_hku": False}
        self.calls: list[str] = []

    def complete_json(self, *, task: str, model: str, system: str, user: str, context: dict[str, Any]) -> LLMResult:
        self.calls.append(task)
        if task == "intent":
            return LLMResult(data=self.intent, model="scripted")
        item = self.answers.pop(0)
        if isinstance(item, Exception):
            raise item
        return LLMResult(data=item, model="scripted")


@pytest.fixture
def policy() -> Policy:
    return get_policy()


@pytest.fixture
def make_pipeline(policy: Policy, tmp_path: Path):  # type: ignore[no-untyped-def]
    def _make(llm: Any = None, retriever: Any = None, demo_cache: str = "off", tau: float = 0.7) -> Pipeline:
        settings = load_settings(
            env_file=tmp_path / "missing.env",
            text_provider="mock" if llm is not None else "none",
            retrieve_tau=tau,
            demo_cache=demo_cache,
            demo_cache_path=tmp_path / "demo_cache.json",
        )
        deps = PipelineDeps(
            settings=settings,
            policy=policy,
            retriever=retriever or FakeRetriever(),
            store=STORE,
            llm=llm,
            vision=UnavailableVisionProvider(),
            demo_cache=DemoCache(settings.demo_cache_path),
            vocabulary=["Paper", "Metal", "Plastic", "Glass Bottle", "Tetra Pak", "Rechargeable Battery", "blue bin"],
        )
        return Pipeline(deps)

    return _make


__all__ = ["CHUNKS", "STORE", "FakeRetriever", "ScriptedLLM", "make_chunk", "MockTextLLM", "ProviderError"]
