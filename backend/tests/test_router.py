from backend.app.policy.router import route_intent, route_retrieval
from backend.app.schemas import ScoredChunk

from .conftest import STORE, make_chunk


def sc(chunk_id: str, score: float) -> ScoredChunk:
    return ScoredChunk(chunk=STORE[chunk_id], score=score)


def route(policy, message, hits, hazard=(), items=(), tau=0.7):
    return route_retrieval(
        message=message, items=list(items), retrieved=hits, hazardous_candidates=list(hazard),
        tau=tau, max_selected=3, policy=policy,
    )


def test_rows_1_and_2_from_intent(policy):
    assert route_intent("offcampus", policy).reason_code == "OUT_OF_SCOPE_LOCATION"
    assert route_intent("penalty_appeal", policy).reason_code == "OUT_OF_SCOPE_PENALTY"
    assert route_intent("disposal_application", policy).reason_code == "OUT_OF_SCOPE_APPLICATION"
    assert route_intent("offtopic_or_injection", policy).reason_code == "OUT_OF_SCOPE_OFFTOPIC"
    r = route_intent("onsite_sign_conflict", policy)
    assert (r.action, r.reason_code) == ("defer", "ONSITE_SIGN_CONFLICT")
    assert route_intent("recycling_question", policy) is None


def test_row3_hazard_keyword_gives_official_excerpts_only(policy):
    r = route(policy, "Where do I put used AA batteries?", [sc("plastic-do", 0.8)],
              hazard=[sc("battery-dont", 0.75), sc("battery-do", 0.7)])
    assert (r.action, r.reason_code) == ("defer", "HAZARDOUS_OFFICIAL_LINKS_ONLY")
    assert [c.chunk.chunk_id for c in r.chunks] == ["battery-dont", "battery-do"]


def test_row3_hazard_keyword_without_official_guidance_refuses(policy):
    r = route(policy, "How do I dispose of expired medicine?", [sc("plastic-do", 0.8)])
    assert (r.action, r.reason_code) == ("refuse", "NO_UNIFIED_STANDARD")


def test_row3_hazard_chunk_as_best_match_without_keyword(policy):
    r = route(policy, "Where do old vape pens go?", [sc("battery-do", 0.8), sc("plastic-do", 0.75)])
    assert r.reason_code == "HAZARDOUS_OFFICIAL_LINKS_ONLY"


def test_row4_unsupported_item_beats_a_battery_chunk(policy):
    r = route(policy, "Where do I put an old phone charger?", [sc("battery-do", 0.8)])
    assert (r.action, r.reason_code) == ("refuse", "NO_UNIFIED_STANDARD")


def test_row4_no_standard_chunk_strictest_tier_wins(policy):
    nus = make_chunk("nus", "Furniture is handled by halls", tier="no_unified_standard", applies_to=("sofa",))
    general = make_chunk("gen", "Plastic", stream="Plastic", line=9)
    r = route(policy, "Where does my old sofa cushion go?",
              [ScoredChunk(chunk=general, score=0.9), ScoredChunk(chunk=nus, score=0.8)])
    assert r.reason_code == "NO_UNIFIED_STANDARD"


def test_unrelated_strict_chunk_is_dropped_not_blocking(policy):
    # A battery chunk above tau that is not the best match and not about this item.
    r = route(policy, "Where does a plastic bottle go?", [sc("plastic-do", 0.85), sc("battery-do", 0.75)])
    assert r.is_answer
    assert [c.chunk.chunk_id for c in r.chunks] == ["plastic-do"]


def test_row5_low_retrieval_match(policy):
    r = route(policy, "Can I recycle a yoga mat?", [sc("plastic-do", 0.6), sc("metal-do", 0.55)])
    assert (r.action, r.reason_code) == ("refuse", "LOW_RETRIEVAL_MATCH")


def test_row6_answer_keeps_at_most_three_and_dedupes_identical_text(policy):
    dup = make_chunk("plastic-do-copy", "Beverage plastic bottles", stream="Plastic", line=20)
    hits = [sc("plastic-do", 0.9), ScoredChunk(chunk=dup, score=0.89), sc("metal-do", 0.8),
            sc("metal-dont", 0.78), sc("smart-glass", 0.75)]
    r = route(policy, "Where does a plastic bottle go?", hits)
    assert r.is_answer and r.reason_code == "OK"
    assert [c.chunk.chunk_id for c in r.chunks] == ["plastic-do", "metal-do", "metal-dont"]
