"""FR-2 deterministic boundary rules and whole-word term matching."""

from __future__ import annotations

import re
from collections.abc import Iterable
from dataclasses import dataclass

from . import Policy


@dataclass(frozen=True)
class RuleHit:
    intent: str
    pattern: str


def check_boundary_rules(message: str, policy: Policy) -> RuleHit | None:
    """Return the first rule group that matches, or None.

    Precision-first: these rules can only force a refusal/deferral. Anything
    they miss is left to the LLM intent call and, after that, to retrieval.
    """
    for rule in policy.boundary_rules:
        for pattern in rule.patterns:
            if pattern.search(message):
                return RuleHit(intent=rule.intent, pattern=pattern.pattern)
    return None


def _term_regex(term: str) -> re.Pattern[str]:
    # Whole-word, case-insensitive, flexible whitespace/hyphen between words.
    parts = [re.escape(p) for p in re.split(r"[\s-]+", term.strip()) if p]
    return re.compile(r"(?<![a-z0-9])" + r"[\s-]+".join(parts) + r"(?![a-z0-9])", re.IGNORECASE)


_TERM_CACHE: dict[str, re.Pattern[str]] = {}


def match_terms(texts: Iterable[str], terms: Iterable[str]) -> list[str]:
    """Return the terms that occur as whole words in any of `texts`."""
    haystack = "\n".join(t for t in texts if t)
    found: list[str] = []
    for term in terms:
        rx = _TERM_CACHE.get(term)
        if rx is None:
            rx = _TERM_CACHE[term] = _term_regex(term)
        if rx.search(haystack):
            found.append(term)
    return found
