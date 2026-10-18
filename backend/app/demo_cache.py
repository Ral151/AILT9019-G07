"""FR-10 demo cache: pre-generated, human-reviewed answers for the sample
questions only. Built by scripts/build_demo_cache.py; an entry is served only
after a person sets "reviewed": true in demo_cache.json. Images are never
cached (R8)."""

from __future__ import annotations

import json
import re
from pathlib import Path

from .schemas import ApiResponse


def normalise_question(text: str) -> str:
    return re.sub(r"\s+", " ", re.sub(r"[^a-z0-9 ]", " ", text.lower())).strip()


class DemoCache:
    def __init__(self, path: Path) -> None:
        self.entries: dict[str, ApiResponse] = {}
        if not path.exists():
            return
        raw = json.loads(path.read_text(encoding="utf-8"))
        for entry in raw.get("entries", []):
            if entry.get("reviewed") is True:
                self.entries[normalise_question(entry["question"])] = ApiResponse.model_validate(entry["response"])

    def lookup(self, question: str, request_id: str) -> ApiResponse | None:
        hit = self.entries.get(normalise_question(question))
        if hit is None:
            return None
        return hit.model_copy(update={"request_id": request_id, "served_from_cache": True})
