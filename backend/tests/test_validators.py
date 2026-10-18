import pytest
from pydantic import ValidationError

from backend.app.policy.validators import (
    build_citation,
    canonical_stream,
    check_excerpts,
    check_response_invariants,
    validate_generation,
)
from backend.app.schemas import ApiResponse, GenerationOutput

from .conftest import STORE

VOCAB = ["Paper", "Metal", "Plastic", "Glass Bottle", "Tetra Pak", "Rechargeable Battery", "blue bin", "general refuse"]
SELECTED = [STORE["plastic-do"], STORE["metal-do"], STORE["metal-dont"]]


def gen(**kw):
    base = {"bin_category": "Plastic", "answer_text": "Beverage plastic bottles go in Plastic.", "used_chunk_ids": ["plastic-do"]}
    base.update(kw)
    return GenerationOutput.model_validate(base)


def test_valid_answer_passes():
    assert validate_generation(gen(), SELECTED, VOCAB) == []


def test_check1_unknown_chunk_id():
    errors = validate_generation(gen(used_chunk_ids=["plastic-do", "invented"]), SELECTED, VOCAB)
    assert any("not in the provided excerpts" in e for e in errors)


def test_check2_bin_must_match_a_cited_stream():
    errors = validate_generation(gen(bin_category="Metal"), SELECTED, VOCAB)
    assert any("not the stream of a cited excerpt" in e for e in errors)
    # A DON'T chunk has no stream, so it can never justify a bin.
    errors = validate_generation(
        gen(bin_category="Metal", answer_text="Aerosol cans go in Metal.", used_chunk_ids=["metal-dont"]), SELECTED, VOCAB
    )
    assert errors


def test_check4_answer_cannot_name_an_uncited_bin():
    errors = validate_generation(gen(answer_text="It goes in the blue bin."), SELECTED, VOCAB)
    assert any("'blue bin'" in e for e in errors)
    errors = validate_generation(gen(answer_text="Plastic, not Metal."), SELECTED, VOCAB)
    assert any("'Metal'" in e for e in errors)
    # Citing the metal chunk too makes the same sentence valid.
    assert validate_generation(gen(answer_text="Plastic, not Metal.", used_chunk_ids=["plastic-do", "metal-do"]), SELECTED, VOCAB) == []


def test_plural_forms_match_cited_text():
    assert validate_generation(gen(answer_text="Plastics bottles are accepted under Plastic."), SELECTED, VOCAB) == []


def test_canonical_stream_uses_corpus_spelling():
    assert canonical_stream("plastic", [STORE["plastic-do"]]) == "Plastic"
    assert canonical_stream(None, [STORE["plastic-do"]]) is None


def test_excerpts_must_be_verbatim():
    good = ApiResponse(request_id="r", action="answer", reason_code="OK", answer_text="x", bin_category="Plastic",
                       citations=[build_citation(STORE["plastic-do"])])
    assert check_excerpts(good, STORE) == []
    tampered = good.model_copy(update={"citations": [build_citation(STORE["plastic-do"]).model_copy(update={"excerpt": "Any plastic"})]})
    assert check_excerpts(tampered, STORE)


def test_hazardous_answer_must_be_the_template():
    r = ApiResponse(request_id="r", action="defer", reason_code="HAZARDOUS_OFFICIAL_LINKS_ONLY", answer_text="Put it in the bin.")
    assert check_response_invariants(r, STORE, hazardous_template="TEMPLATE")


@pytest.mark.parametrize(
    "payload",
    [
        {"action": "refuse", "reason_code": "LOW_RETRIEVAL_MATCH", "bin_category": "Plastic"},
        {"action": "answer", "reason_code": "OK", "bin_category": "Plastic", "citations": []},
        {"action": "answer", "reason_code": "LOW_RETRIEVAL_MATCH"},
    ],
)
def test_response_invariants_are_enforced_by_the_schema(payload):
    with pytest.raises(ValidationError):
        ApiResponse(request_id="r", answer_text="x", **payload)


def test_generation_schema_rejects_bad_output():
    with pytest.raises(ValidationError):
        GenerationOutput.model_validate({"bin_category": "Plastic", "answer_text": "", "used_chunk_ids": []})
    assert GenerationOutput.model_validate({"bin_category": " ", "answer_text": "x", "used_chunk_ids": ["a"]}).bin_category is None
