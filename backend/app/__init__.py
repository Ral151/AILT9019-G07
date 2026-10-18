"""Flask application factory.

    flask --app backend.app run --debug
"""

from __future__ import annotations

import logging
import time
from dataclasses import dataclass
from typing import Any

from flask import Flask, jsonify, request, send_from_directory

from .config import REPO_ROOT, Settings, load_settings
from .observability import RateLimiter, log_request
from .providers.llm import OpenAICompatibleLLM
from .workflow import Pipeline, PipelineDeps, Trace

FRONTEND_DIST = REPO_ROOT / "frontend" / "dist"


@dataclass
class AppState:
    settings: Settings
    deps: PipelineDeps
    store: Any
    pipeline: Pipeline
    rate_limiter: RateLimiter
    _ping_cache: tuple[float, bool | None] = (0.0, None)

    def log_request(self, response: Any, trace: Trace, latency_s: float) -> None:
        log_request(response, trace, latency_s, self.settings.text_provider)

    def provider_reachable(self) -> bool | None:
        llm = self.deps.llm
        inner = getattr(llm, "inner", llm)
        if not isinstance(inner, OpenAICompatibleLLM):
            return None
        checked_at, value = self._ping_cache
        if time.monotonic() - checked_at > 60:
            value = inner.ping()
            self._ping_cache = (time.monotonic(), value)
        return value


def create_app(settings: Settings | None = None, deps: PipelineDeps | None = None, store: Any = None) -> Flask:
    settings = settings or load_settings()
    if deps is None:
        from .services import build_deps

        deps, store = build_deps(settings)

    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s %(message)s")
    app = Flask(__name__, static_folder=None)
    app.config["MAX_CONTENT_LENGTH"] = settings.max_image_bytes + 64 * 1024
    app.extensions["recycling"] = AppState(
        settings=settings,
        deps=deps,
        store=store,
        pipeline=Pipeline(deps),
        rate_limiter=RateLimiter(settings.rate_limit_per_min),
    )

    from .routes import api_bp

    app.register_blueprint(api_bp)

    @app.after_request
    def _cors_and_headers(resp: Any) -> Any:
        origin = request.headers.get("Origin")
        if origin and origin in settings.cors_origins:
            resp.headers["Access-Control-Allow-Origin"] = origin
            resp.headers["Vary"] = "Origin"
        resp.headers.setdefault("X-Content-Type-Options", "nosniff")
        return resp

    @app.errorhandler(413)
    def _too_large(_: Any) -> Any:
        return jsonify({"error": "image_too_large", "detail": "Photos must be 5 MB or smaller."}), 413

    # Serve the built React app (npm --prefix frontend run build).
    @app.get("/")
    @app.get("/<path:path>")
    def frontend(path: str = "index.html") -> Any:
        if path.startswith("api/"):
            return jsonify({"error": "not_found"}), 404
        if not FRONTEND_DIST.exists():
            return (
                "Frontend not built. Run `npm --prefix frontend run dev` (http://localhost:5173) "
                "or `npm --prefix frontend run build`.",
                200,
                {"Content-Type": "text/plain; charset=utf-8"},
            )
        target = FRONTEND_DIST / path
        if path != "index.html" and target.is_file():
            return send_from_directory(FRONTEND_DIST, path)
        return send_from_directory(FRONTEND_DIST, "index.html")

    return app
