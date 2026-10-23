"""FR-6 citation and answer validation.

The server, not the LLM, builds every citation: excerpts are copied from the
stored chunk text (R9). An LLM answer is accepted only if all checks pass.
"""

from __future__ import annotations

import re
from collections.abc import Iterable, Mapping, Sequence

from ..schemas import ApiResponse, Chunk, Citation, GenerationOutput
from . import Policy


def build_citation(chunk: Chunk) -> Citation:
    return Citation(
        source_id=chunk.source_id,
        title=chunk.doc_title,
        section=chunk.section,
        lines=chunk.lines,
        excerpt=chunk.text,
        url=chunk.url,
        retrieved_at=chunk.retrieved_at,
    )


def _strip_plural(word: str) -> str:
    """Strip a regular English plural ending without mangling words that
    genuinely end in 's' (glass, bus) or are too short."""
    if len(word) <= 3:
        return word
    if word.endswith("ies") and len(word) > 4:
        return word[:-3] + "y"  # batteries -> battery
    # Only true "-es" plurals (ss/x/ch/sh/z + es) lose the "es"; a word like
    # "bottles" is "bottle" + "s" and must only lose the final "s".
    if word.endswith(("sses", "xes", "ches", "shes", "zes")) and len(word) > 4:
        return word[:-2]  # glasses -> glass, boxes -> box
    if word.endswith("s") and not word.endswith(("ss", "us", "is", "os")):
        return word[:-1]  # bottles -> bottle
    return word


def _norm(text: str) -> str:
    """Lowercase, collapse to alnum tokens, and lightly strip regular English
    plural endings so singular/plural forms compare equal."""
    words = re.findall(r"[a-z0-9]+", text.lower())
    return " " + " ".join(_strip_plural(w) for w in words) + " "


def bin_vocabulary(policy: Policy, streams: Iterable[str]) -> list[str]:
    """Stream names from the corpus plus generic bin words from policy."""
    vocab = {s.strip() for s in streams if s and s.strip()}
    vocab.update(policy.bin_vocabulary_extra)
    return sorted(vocab, key=len, reverse=True)


def validate_generation(
    output: GenerationOutput,
    selected: Sequence[Chunk],
    vocabulary: Sequence[str],
) -> list[str]:
    """Return the list of FR-6 violations (empty means the answer is valid)."""
    errors: list[str] = []
    by_id = {c.chunk_id: c for c in selected}

    # 1. Every used chunk id was in the selected set.
    unknown = [cid for cid in output.used_chunk_ids if cid not in by_id]
    if unknown:
        errors.append(f"used_chunk_ids not in the provided excerpts: {unknown}")
    cited = [by_id[cid] for cid in output.used_chunk_ids if cid in by_id]
    if not cited:
        errors.append("no valid used_chunk_ids")
        return errors

    # 2. bin_category equals the stream of at least one cited chunk.
    if output.bin_category is not None:
        streams = {c.stream.casefold() for c in cited if c.stream}
        if output.bin_category.strip().casefold() not in streams:
            errors.append(
                f"bin_category {output.bin_category!r} is not the stream of a cited excerpt "
                f"(cited streams: {sorted(streams) or 'none'})"
            )

    # 4. answer_text names no bin/stream that the cited chunks don't name.
    cited_text = _norm(" ".join(f"{c.section} {c.stream or ''} {c.text}" for c in cited))
    answer = _norm(output.answer_text)
    for term in vocabulary:
        t = _norm(term)
        if t in answer and t not in cited_text:
            errors.append(f"answer_text mentions {term!r}, which no cited excerpt mentions")

    # 3. (excerpts are copied by the server) is enforced by build_citation and
    #    re-checked on the final response with check_excerpts.
    return errors


def canonical_stream(bin_category: str | None, cited: Sequence[Chunk]) -> str | None:
    """Return the corpus spelling of the stream the LLM named."""
    if bin_category is None:
        return None
    for c in cited:
        if c.stream and c.stream.casefold() == bin_category.strip().casefold():
            return c.stream
    return None


def check_excerpts(response: ApiResponse, store: Mapping[str, Chunk]) -> list[str]:
    """FR-7 invariant: every excerpt is a substring of its stored chunk."""
    errors: list[str] = []
    stored = {(c.source_id, c.lines): c.text for c in store.values()}
    for cit in response.citations:
        text = stored.get((cit.source_id, cit.lines))
        if text is None:
            errors.append(f"citation {cit.source_id}:{cit.lines} is not in the corpus")
        elif cit.excerpt not in text:
            errors.append(f"excerpt for {cit.source_id}:{cit.lines} is not verbatim")
    return errors


def check_response_invariants(
    response: ApiResponse, store: Mapping[str, Chunk], hazardous_template: str
) -> list[str]:
    """All FR-7 invariants, for tests and the eval harness."""
    errors = check_excerpts(response, store)
    if response.bin_category is not None and (
        response.action not in ("answer", "answer_with_caveat") or not response.citations
    ):
        errors.append("bin_category without an answer action and a citation")
    if response.action in ("defer", "refuse") and response.bin_category is not None:
        errors.append("defer/refuse carries a bin_category")
    if response.reason_code == "HAZARDOUS_OFFICIAL_LINKS_ONLY" and response.answer_text != hazardous_template:
        errors.append("hazardous answer_text is not the fixed template")
    return errors
