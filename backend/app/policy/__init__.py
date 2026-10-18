"""Deterministic policy: boundary rules, router, templates, validators."""

from __future__ import annotations

import re
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path

import yaml

from ..schemas import Redirect

POLICY_FILE = Path(__file__).with_name("policy.yaml")


@dataclass(frozen=True)
class BoundaryRule:
    intent: str
    patterns: tuple[re.Pattern[str], ...]


@dataclass(frozen=True)
class Template:
    reason_code: str
    action: str
    text: str
    redirect: Redirect | None


@dataclass(frozen=True)
class Policy:
    version: int
    boundary_rules: tuple[BoundaryRule, ...]
    hazardous_items: tuple[str, ...]
    unsupported_items: tuple[str, ...]
    bin_vocabulary_extra: tuple[str, ...]
    redirects: dict[str, Redirect]
    templates: dict[str, Template]
    caveats: dict[str, str]
    samples: tuple[str, ...]

    def template(self, key: str) -> Template:
        return self.templates[key]


def _redirect(redirects: dict[str, Redirect], key: str | None) -> Redirect | None:
    if key is None:
        return None
    return redirects[key]


def load_policy(path: Path = POLICY_FILE) -> Policy:
    raw = yaml.safe_load(path.read_text(encoding="utf-8"))
    redirects = {k: Redirect(**v) for k, v in raw["redirects"].items()}
    templates = {
        key: Template(
            reason_code=key if not key.startswith("IMAGE_SERVICE") else "SERVICE_UNAVAILABLE",
            action=value["action"],
            text=" ".join(value["text"].split()),
            redirect=_redirect(redirects, value.get("redirect")),
        )
        for key, value in raw["templates"].items()
    }
    rules = tuple(
        BoundaryRule(
            intent=group["intent"],
            patterns=tuple(re.compile(p, re.IGNORECASE) for p in group["patterns"]),
        )
        for group in raw["boundary_rules"]
    )
    return Policy(
        version=int(raw["version"]),
        boundary_rules=rules,
        hazardous_items=tuple(raw["hazardous_items"]),
        unsupported_items=tuple(raw["unsupported_items"]),
        bin_vocabulary_extra=tuple(raw["bin_vocabulary_extra"]),
        redirects=redirects,
        templates=templates,
        caveats={k: " ".join(v.split()) for k, v in raw["caveats"].items()},
        samples=tuple(raw["samples"]),
    )


@lru_cache(maxsize=1)
def get_policy() -> Policy:
    return load_policy()
