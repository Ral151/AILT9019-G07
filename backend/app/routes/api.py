"""JSON API (FR-7): POST /api/ask, GET /api/health, GET /api/samples."""

from __future__ import annotations

import time
import uuid
from typing import Any

from flask import Blueprint, current_app, jsonify, request

from ..schemas import ErrorResponse

bp = Blueprint("api", __name__, url_prefix="/api")


def _error(status: int, error: str, detail: str | None = None) -> Any:
    return jsonify(ErrorResponse(error=error, detail=detail).model_dump(exclude_none=True)), status


@bp.post("/ask")
async def ask() -> Any:
    state = current_app.extensions["recycling"]
    settings = state.settings
    if not state.rate_limiter.allow(request.remote_addr or "unknown"):
        return _error(429, "rate_limited", "Too many questions. Please wait a minute and try again.")

    if request.is_json:
        payload = request.get_json(silent=True) or {}
        message = str(payload.get("message") or "")
        image_bytes = None
    else:
        message = request.form.get("message", "")
        upload = request.files.get("image")
        # Read into memory only (R8); never saved.
        image_bytes = upload.read(settings.max_image_bytes + 1) if upload else None

    message = message.strip()
    if len(message) > settings.max_message_chars:
        return _error(400, "message_too_long", f"Please keep questions under {settings.max_message_chars} characters.")
    if not message and not image_bytes:
        return _error(400, "empty_request", "Type a question or add a photo.")
    if image_bytes is not None and len(image_bytes) > settings.max_image_bytes:
        return _error(413, "image_too_large", "Photos must be 5 MB or smaller.")

    started = time.perf_counter()
    result = await state.pipeline.run(message, image_bytes=image_bytes, request_id=str(uuid.uuid4()))
    state.log_request(result.response, result.trace, time.perf_counter() - started)
    return jsonify(result.response.model_dump(mode="json"))


@bp.get("/health")
def health() -> Any:
    state = current_app.extensions["recycling"]
    s = state.settings
    return jsonify(
        {
            "status": "ok",
            "corpus_version": state.store.corpus_version,
            "corpus_chunks": len(state.store.chunks),
            "embed_model": s.embed_model,
            "text_provider": s.text_provider,
            "text_model": s.text_model if s.llm_enabled else None,
            "intent_model": s.intent_model if s.llm_enabled else None,
            "text_provider_reachable": state.provider_reachable(),
            "vision_model_primary": s.vision_model_primary,
            "vision_model_fallback": s.vision_model_fallback,
            "vision_enabled": False,  # milestone M4
            "retrieve_tau": s.retrieve_tau,
            "demo_cache": s.demo_cache,
            "demo_cache_entries": len(state.deps.demo_cache.entries),
        }
    )


@bp.get("/samples")
def samples() -> Any:
    state = current_app.extensions["recycling"]
    return jsonify({"samples": list(state.deps.policy.samples)})
