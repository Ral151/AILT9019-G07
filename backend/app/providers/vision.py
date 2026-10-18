"""Vision provider interface (§7.6). The Qwen3-VL implementation, confidence
gate and fallback chain are milestone M4; until then every photo gets the
text-only fallback ("please describe the item")."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol


@dataclass(frozen=True)
class VisionItem:
    label: str
    free_text_name: str
    material_guess: str
    confidence: float


@dataclass(frozen=True)
class VisionResult:
    image_quality: str  # ok | blurry | dark | no_waste_item
    items: tuple[VisionItem, ...]
    model: str


class VisionUnavailable(RuntimeError):
    pass


class VisionProvider(Protocol):
    def classify(self, image_bytes: bytes, mime: str) -> VisionResult: ...


class UnavailableVisionProvider:
    """Used until M4: always falls through to the text-only message."""

    def classify(self, image_bytes: bytes, mime: str) -> VisionResult:
        raise VisionUnavailable("vision provider not implemented yet (milestone M4)")
