"""Unit tests for the eval harness scoring and critical-failure logic.

These functions decide the release gate (PASS/FAIL), so they get their own
tests instead of being trusted implicitly. Uses the small corpus from
conftest.py; the fake pipeline output is built directly from ApiResponse.
"""

from __future__ import annotations

from backend.app.policy.validators import build_citation
from backend.app.schemas import ApiResponse
from backend.app.workflow import PipelineResult, Trace
from eval.run_eval import detect_critical, score_case

from .conftest import STORE

HAZ_TMPL = "TEMPLATE"


def _result(
    action,
    reason,
    *,
    bin_category=None,
    answer_text="x",
    citations=(),
    selected=(),
):
    resp = ApiResponse(
        request_id="r",
        action=action,
        reason_code=reason,
        answer_text=answer_text,
        bin_category=bin_category,
        citations=list(citations),
    )
    return PipelineResult(response=resp, trace=Trace(selected=list(selected)))


# --------------------------------------------------------------------------
# score_case
# --------------------------------------------------------------------------


def test_score_category_matches_gold():
    case = {"gold": {"bin_category": ["Plastic"], "action": ["answer"], "reason_code": "OK", "must_include": []}}
    good = _result(
        "answer", "OK", bin_category="Plastic",
        citations=[build_citation(STORE["plastic-do"])], selected=["plastic-do"],
    )
    assert score_case(case, good, STORE)["category"] == 1
    bad = _result(
        "answer", "OK", bin_category="Metal",
        citations=[build_citation(STORE["metal-do"])], selected=["metal-do"],
    )
    assert score_case(case, bad, STORE)["category"] == 0


def test_score_safety_checks_action_and_reason():
    case = {"gold": {"action": ["answer"], "reason_code": "OK", "must_include": []}}
    assert score_case(case, _result("answer", "OK"), STORE)["safety"] == 1
    assert score_case(case, _result("refuse", "LOW_RETRIEVAL_MATCH"), STORE)["safety"] == 0


def test_score_safety_checks_must_include():
    case = {"gold": {"action": ["refuse"], "reason_code": "NO_UNIFIED_STANDARD", "must_include": ["hall tutor"]}}
    ok = _result("refuse", "NO_UNIFIED_STANDARD", answer_text="Please ask your hall tutor.")
    assert score_case(case, ok, STORE)["safety"] == 1
    missing = _result("refuse", "NO_UNIFIED_STANDARD", answer_text="Please ask someone else.")
    assert score_case(case, missing, STORE)["safety"] == 0


def test_score_citation_required_and_allowed():
    case = {"gold": {"citations": [{"chunk_id": "plastic-do", "required": True}], "action": ["answer"], "reason_code": "OK", "must_include": []}}
    good = _result(
        "answer", "OK", bin_category="Plastic",
        citations=[build_citation(STORE["plastic-do"])], selected=["plastic-do"],
    )
    assert score_case(case, good, STORE)["citation"] == 1
    # Citing a chunk the gold labels don't allow fails the citation dimension.
    bad = _result(
        "answer", "OK", bin_category="Plastic",
        citations=[build_citation(STORE["metal-do"])], selected=["metal-do"],
    )
    assert score_case(case, bad, STORE)["citation"] == 0


# --------------------------------------------------------------------------
# detect_critical
# --------------------------------------------------------------------------


def test_cf1_bin_category_needs_a_retrieved_citation():
    # bin category claims Plastic, but the cited chunk was never retrieved.
    r = _result(
        "answer", "OK", bin_category="Plastic",
        citations=[build_citation(STORE["plastic-do"])], selected=["metal-do"],
    )
    assert any("CF1" in f for f in detect_critical({"tags": []}, r, STORE, HAZ_TMPL))


def test_cf2_must_defer_to_onsite_sign():
    r = _result(
        "answer", "OK", bin_category="Plastic",
        citations=[build_citation(STORE["plastic-do"])], selected=["plastic-do"],
    )
    assert any("CF2" in f for f in detect_critical({"tags": ["onsite_sign_conflict"]}, r, STORE, HAZ_TMPL))


def test_cf3_must_refuse_offcampus():
    r = _result(
        "answer", "OK", bin_category="Plastic",
        citations=[build_citation(STORE["plastic-do"])], selected=["plastic-do"],
    )
    assert any("CF3" in f for f in detect_critical({"tags": ["offcampus"]}, r, STORE, HAZ_TMPL))


def test_cf4_hazardous_answer_must_be_the_template():
    r = _result("defer", "HAZARDOUS_OFFICIAL_LINKS_ONLY", answer_text="Put it in the bin.")
    assert any("CF4" in f for f in detect_critical({"tags": ["hazardous"]}, r, STORE, HAZ_TMPL))


def test_cf5_unsupported_item_gets_no_bin():
    r = _result(
        "answer", "OK", bin_category="Plastic",
        citations=[build_citation(STORE["plastic-do"])], selected=["plastic-do"],
    )
    assert any("CF5" in f for f in detect_critical({"tags": ["unsupported_item"]}, r, STORE, HAZ_TMPL))


def test_cf6_unclear_image_must_ask_for_clearer_input():
    r = _result("refuse", "LOW_IMAGE_CONFIDENCE")
    assert any("CF6" in f for f in detect_critical({"tags": ["low_quality_image"]}, r, STORE, HAZ_TMPL))


def test_valid_answer_has_no_critical_failure():
    r = _result(
        "answer", "OK", bin_category="Plastic",
        citations=[build_citation(STORE["plastic-do"])], selected=["plastic-do"],
    )
    assert detect_critical({"tags": []}, r, STORE, HAZ_TMPL) == []
