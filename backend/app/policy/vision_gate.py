"""Deterministic confidence gate for photos (R7, §7.4).

A photo proceeds only if all hold: image_quality is ok, exactly one item, its
label is on the closed list, confidence >= min_conf, and the label beats the
best different alternative by >= margin. Anything else asks for clearer input.
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass

from ..providers.vision import VisionResult


@dataclass(frozen=True)
class GateDecision:
    template_key: str | None  # None = proceed with `label`
    label: str = ""
    confidence: float = 0.0


def gate_vision(result: VisionResult, labels: Sequence[str], *, min_conf: float, margin: float) -> GateDecision:
    if result.image_quality == "blurry" or result.image_quality == "dark":
        return GateDecision("IMAGE_UNREADABLE")
    if result.image_quality != "ok" or not result.items:
        return GateDecision("LOW_IMAGE_CONFIDENCE")
    if len(result.items) > 1:
        return GateDecision("MULTIPLE_ITEMS")

    item = result.items[0]
    by_key = {label.casefold(): label for label in labels}
    label = by_key.get(item.label.casefold())
    if label is None:  # "other" or a label the model made up
        return GateDecision("LOW_IMAGE_CONFIDENCE", confidence=item.confidence)
    if item.confidence < min_conf:
        return GateDecision("LOW_IMAGE_CONFIDENCE", label=label, confidence=item.confidence)
    runner_up = max(
        (a.confidence for a in item.alternatives if a.label.casefold() != label.casefold()),
        default=0.0,
    )
    if item.confidence - runner_up < margin:
        return GateDecision("LOW_IMAGE_CONFIDENCE", label=label, confidence=item.confidence)
    return GateDecision(None, label=label, confidence=item.confidence)
