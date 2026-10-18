"""FR-4 deterministic policy router.

Rows are evaluated top to bottom; the first match wins. The LLM never sees or
overrules these decisions: it only writes the short answer on row 6.

  1  out-of-scope intent                   -> refuse  OUT_OF_SCOPE_*
  2  on-site sign / staff conflict         -> defer   ONSITE_SIGN_CONFLICT
  3  hazardous item / hazardous chunk      -> defer   HAZARDOUS_OFFICIAL_LINKS_ONLY
  4  unsupported item / no-standard chunk  -> refuse  NO_UNIFIED_STANDARD
  5  nothing above tau                     -> refuse  LOW_RETRIEVAL_MATCH
  6  general rule                          -> answer  (6b: with caveat, decided
                                                       after generation from the
                                                       chunks actually cited)

Within rows 3-4, items named on the policy lists (hazardous_items,
unsupported_items) are decided first; strict corpus chunks second.

"Strictest tier wins": a hazardous or no-standard chunk overrides general
chunks when it is about the same item, i.e. it is the best match, or the
user's message/items contain one of the chunk's reviewed `applies_to` terms.
Strict chunks about other items are dropped rather than blocking an answer.
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass, field

from ..schemas import ScoredChunk
from . import Policy
from .rules import match_terms

INTENT_TEMPLATES: dict[str, str] = {
    "offcampus": "OUT_OF_SCOPE_LOCATION",
    "penalty_appeal": "OUT_OF_SCOPE_PENALTY",
    "disposal_application": "OUT_OF_SCOPE_APPLICATION",
    "offtopic_or_injection": "OUT_OF_SCOPE_OFFTOPIC",
    "onsite_sign_conflict": "ONSITE_SIGN_CONFLICT",
}

GENERAL_TIERS = frozenset({"general_recyclable", "info"})


@dataclass(frozen=True)
class Route:
    """Router decision.

    `template_key` is set for every defer/refuse; it is None only for the
    answer path, where `chunks` are the chunks handed to the generator.
    For the hazardous path, `chunks` are the official excerpts to show.
    """

    action: str
    reason_code: str
    template_key: str | None
    chunks: tuple[ScoredChunk, ...] = ()
    matched_terms: tuple[str, ...] = field(default_factory=tuple)
    row: int = 0

    @property
    def is_answer(self) -> bool:
        return self.template_key is None


def _template_route(key: str, policy: Policy, row: int, **kwargs: object) -> Route:
    t = policy.template(key)
    return Route(action=t.action, reason_code=t.reason_code, template_key=key, row=row, **kwargs)  # type: ignore[arg-type]


def route_intent(intent: str, policy: Policy) -> Route | None:
    """Rows 1-2. Returns None for `recycling_question`."""
    key = INTENT_TEMPLATES.get(intent)
    if key is None:
        return None
    return _template_route(key, policy, row=1 if key != "ONSITE_SIGN_CONFLICT" else 2)


def _dedupe_by_best(chunks: Sequence[ScoredChunk]) -> list[ScoredChunk]:
    """Keep the best-scoring chunk per id, and per identical text (the poster
    and the photo guide repeat many items word for word)."""
    best: dict[str, ScoredChunk] = {}
    for sc in sorted(chunks, key=lambda s: s.score, reverse=True):
        key = " ".join(sc.chunk.text.casefold().split())
        if key not in best:
            best[key] = sc
    return list(best.values())


def route_retrieval(
    *,
    message: str,
    items: Sequence[str],
    retrieved: Sequence[ScoredChunk],
    hazardous_candidates: Sequence[ScoredChunk],
    tau: float,
    max_selected: int,
    policy: Policy,
) -> Route:
    """Rows 3-6, given the retrieval results for this question."""
    texts = [message, *items]
    ranked = _dedupe_by_best(retrieved)
    above = [sc for sc in ranked if sc.score >= tau]
    top_id = above[0].chunk.chunk_id if above else None

    def applies(sc: ScoredChunk) -> bool:
        return sc.chunk.chunk_id == top_id or bool(match_terms(texts, sc.chunk.applies_to))

    hazard_pool = _dedupe_by_best(
        [*hazardous_candidates, *(sc for sc in ranked if sc.chunk.rule_tier == "hazardous_unified")]
    )

    # Rows 3-4, keyword part first: the policy lists name the item outright,
    # which is more reliable than which chunk happens to score highest.
    hazard_terms = tuple(match_terms(texts, policy.hazardous_items))
    if hazard_terms:
        relevant = [sc for sc in hazard_pool if match_terms(texts, sc.chunk.applies_to)]
        if relevant:
            return _template_route(
                "HAZARDOUS_OFFICIAL_LINKS_ONLY",
                policy,
                row=3,
                chunks=tuple(relevant[:max_selected]),
                matched_terms=hazard_terms,
            )
        # Hazardous, but the corpus has no official guidance for this item.
        return _template_route("NO_UNIFIED_STANDARD", policy, row=4, matched_terms=hazard_terms)
    unsupported_terms = tuple(match_terms(texts, policy.unsupported_items))
    if unsupported_terms:
        return _template_route("NO_UNIFIED_STANDARD", policy, row=4, matched_terms=unsupported_terms)

    # Rows 3-4, corpus part: strict chunks about this item (strictest wins).
    hazard_above = [sc for sc in hazard_pool if sc.score >= tau and applies(sc)]
    if hazard_above:
        return _template_route(
            "HAZARDOUS_OFFICIAL_LINKS_ONLY", policy, row=3, chunks=tuple(hazard_above[:max_selected])
        )
    if any(sc.chunk.rule_tier == "no_unified_standard" and applies(sc) for sc in above):
        return _template_route("NO_UNIFIED_STANDARD", policy, row=4)

    # Row 5: nothing in the corpus clearly matches.
    selected = [sc for sc in above if sc.chunk.rule_tier in GENERAL_TIERS][:max_selected]
    if not selected:
        return _template_route("LOW_RETRIEVAL_MATCH", policy, row=5)

    # Row 6: answer from the selected chunks (6b decided after generation).
    return Route(action="answer", reason_code="OK", template_key=None, chunks=tuple(selected), row=6)
