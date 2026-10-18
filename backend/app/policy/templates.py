"""Build template-only responses (all defer/refuse paths, FR-4)."""

from __future__ import annotations

from collections.abc import Sequence

from ..schemas import ApiResponse, Chunk, ImageInfo, Redirect
from . import Policy
from .validators import build_citation


def template_response(
    policy: Policy,
    key: str,
    request_id: str,
    *,
    chunks: Sequence[Chunk] = (),
    image: ImageInfo | None = None,
) -> ApiResponse:
    t = policy.template(key)
    redirect: Redirect | None = t.redirect
    citations = [build_citation(c) for c in chunks]
    if key == "HAZARDOUS_OFFICIAL_LINKS_ONLY" and citations:
        redirect = Redirect(label=f"Official source: {citations[0].title}", url=citations[0].url)
    return ApiResponse(
        request_id=request_id,
        action=t.action,  # type: ignore[arg-type]
        reason_code=t.reason_code,  # type: ignore[arg-type]
        answer_text=t.text,
        bin_category=None,
        caveats=[],
        citations=citations,
        redirect=redirect,
        image=image,
    )
