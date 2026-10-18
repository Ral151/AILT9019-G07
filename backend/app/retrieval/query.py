"""Deterministic query clean-up before embedding.

Questions like "Where should I put an empty plastic water bottle?" embed
mostly as "a question about putting things somewhere", so short corpus items
match each other instead of the user's item. Stripping the question frame
("Where should I put an empty") roughly halved top-1 misses on the dev split.
"""

from __future__ import annotations

import re

_FRAME = re.compile(
    r"^(where|what|which|how|can|could|should|would|do|does|is|are|may)\b.*?"
    r"\b(put|go|goes|recycle|recycled|dispose of|throw away|throw|sort|belong to)\b\s*",
    re.IGNORECASE,
)
_LEAD = re.compile(r"^(a|an|the|my|this|these|those|old|used|empty|some)\s+", re.IGNORECASE)


def normalise_query(query: str) -> str:
    q = query.strip().rstrip("?.! ")
    stripped = _FRAME.sub("", q)
    for _ in range(3):
        stripped = _LEAD.sub("", stripped)
    stripped = stripped.strip()
    return stripped if len(stripped) >= 3 else q
