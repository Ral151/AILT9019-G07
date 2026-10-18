"""Versioned prompt files. Changing a prompt means adding a new version file
and re-running the dev split (§0.5)."""

from __future__ import annotations

import hashlib
from functools import lru_cache
from pathlib import Path

PROMPT_DIR = Path(__file__).parent

INTENT_PROMPT = "intent_v1"
ANSWER_PROMPT = "answer_v1"


@lru_cache(maxsize=None)
def load_prompt(name: str) -> str:
    return (PROMPT_DIR / f"{name}.txt").read_text(encoding="utf-8").strip()


def prompt_hash(name: str) -> str:
    return hashlib.sha256(load_prompt(name).encode("utf-8")).hexdigest()[:12]
