"""Pydantic v2 schemas for every API payload and every LLM output (§0.5)."""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

Action = Literal["answer", "answer_with_caveat", "defer", "refuse"]

ReasonCode = Literal[
    "OK",
    "OUT_OF_SCOPE_LOCATION",
    "OUT_OF_SCOPE_PENALTY",
    "OUT_OF_SCOPE_APPLICATION",
    "OUT_OF_SCOPE_OFFTOPIC",
    "ONSITE_SIGN_CONFLICT",
    "HAZARDOUS_OFFICIAL_LINKS_ONLY",
    "NO_UNIFIED_STANDARD",
    "LOW_RETRIEVAL_MATCH",
    "LOW_IMAGE_CONFIDENCE",
    "IMAGE_UNREADABLE",
    "MULTIPLE_ITEMS",
    "VALIDATION_FAILED",
    "SERVICE_UNAVAILABLE",
]

Intent = Literal[
    "recycling_question",
    "onsite_sign_conflict",
    "penalty_appeal",
    "offcampus",
    "disposal_application",
    "offtopic_or_injection",
]

RuleTier = Literal["general_recyclable", "hazardous_unified", "no_unified_standard", "info"]

ANSWER_ACTIONS: frozenset[str] = frozenset({"answer", "answer_with_caveat"})


# --------------------------------------------------------------------------
# Corpus
# --------------------------------------------------------------------------


class Chunk(BaseModel):
    """One rule or list item from the frozen corpus (§6.2)."""

    model_config = ConfigDict(frozen=True)

    chunk_id: str
    source_id: str
    doc_title: str
    url: str
    retrieved_at: str
    section: str
    line_start: int
    line_end: int
    rule_tier: RuleTier
    stream: str | None = None
    caveat_tags: tuple[str, ...] = ()
    applies_to: tuple[str, ...] = ()
    text: str

    @property
    def lines(self) -> str:
        return f"{self.line_start}-{self.line_end}"


class ScoredChunk(BaseModel):
    model_config = ConfigDict(frozen=True)

    chunk: Chunk
    score: float  # cosine similarity, higher is closer


# --------------------------------------------------------------------------
# LLM outputs
# --------------------------------------------------------------------------


class IntentResult(BaseModel):
    """Output of prompt A1 (intent + items)."""

    intent: Intent
    items: list[str] = Field(default_factory=list, max_length=10)
    mentions_location_outside_hku: bool = False

    @field_validator("items")
    @classmethod
    def _clean_items(cls, v: list[str]) -> list[str]:
        return [i.strip()[:80] for i in v if i and i.strip()]


class GenerationOutput(BaseModel):
    """Output of prompt A3 (answer generation).

    `answers_question` extends A3: when the model says the excerpts do not
    answer the question, the router turns the reply into LOW_RETRIEVAL_MATCH.
    It can only make the outcome stricter, never looser.
    """

    answers_question: bool = True
    bin_category: str | None
    answer_text: str = Field(min_length=1, max_length=600)
    used_chunk_ids: list[str] = Field(min_length=1, max_length=3)

    @field_validator("bin_category")
    @classmethod
    def _blank_is_null(cls, v: str | None) -> str | None:
        if v is None:
            return None
        v = v.strip()
        return v or None


# --------------------------------------------------------------------------
# API response (FR-7)
# --------------------------------------------------------------------------


class Citation(BaseModel):
    source_id: str
    title: str
    section: str
    lines: str
    excerpt: str
    url: str
    retrieved_at: str


class Redirect(BaseModel):
    label: str
    url: str


class ImageInfo(BaseModel):
    item_label: str = ""
    confidence: float = 0.0
    needs_clearer_input: bool = False


class ApiResponse(BaseModel):
    request_id: str
    action: Action
    reason_code: ReasonCode
    answer_text: str
    bin_category: str | None = None
    caveats: list[str] = Field(default_factory=list)
    citations: list[Citation] = Field(default_factory=list)
    redirect: Redirect | None = None
    image: ImageInfo | None = None
    served_from_cache: bool = False

    @model_validator(mode="after")
    def _invariants(self) -> "ApiResponse":
        # FR-7 invariants. The excerpt-substring invariant needs the chunk
        # store, so it is checked in policy.validators.check_excerpts.
        if self.bin_category is not None:
            if self.action not in ANSWER_ACTIONS:
                raise ValueError("bin_category set on a non-answer action")
            if not self.citations:
                raise ValueError("bin_category set without a citation")
        if self.action in ("defer", "refuse") and self.bin_category is not None:
            raise ValueError("defer/refuse must not carry a bin_category")
        if self.action in ANSWER_ACTIONS and self.reason_code != "OK":
            raise ValueError("answer actions must use reason_code OK")
        return self


class ErrorResponse(BaseModel):
    error: str
    detail: str | None = None
