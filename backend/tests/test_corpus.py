"""The committed corpus must always pass ingest validation."""

import sys
from pathlib import Path

from backend.app.policy import get_policy
from backend.app.retrieval.corpus import STRICT_TIERS, load_all_chunks

REPO_ROOT = Path(__file__).resolve().parents[2]


def test_corpus_validates_including_html_provenance():
    sys.path.insert(0, str(REPO_ROOT / "scripts"))
    import ingest  # noqa: PLC0415

    manifest, chunks = ingest.validate(require_reviewed=False)
    assert len(chunks) > 50


def test_every_caveat_tag_has_text_and_strict_chunks_have_terms():
    policy = get_policy()
    _, chunks = load_all_chunks()
    for ac in chunks:
        assert set(ac.chunk.caveat_tags) <= set(policy.caveats), ac.chunk.chunk_id
        if ac.chunk.rule_tier in STRICT_TIERS:
            assert ac.chunk.applies_to, ac.chunk.chunk_id


def test_no_hazardous_chunk_is_a_general_answer():
    _, chunks = load_all_chunks()
    battery = [ac.chunk for ac in chunks if "batter" in ac.chunk.text.lower() and "Battery" in ac.chunk.section]
    assert battery and all(c.rule_tier == "hazardous_unified" for c in battery)
