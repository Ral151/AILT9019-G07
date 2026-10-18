"""Privacy-safe request logging (FR-12). Never logs the user's text, image
bytes or EXIF: only ids, outcome, latency, model and token counts."""

from __future__ import annotations

import json
import logging
import time
from collections import defaultdict, deque
from threading import Lock

from .schemas import ApiResponse
from .workflow import Trace

logger = logging.getLogger("hku_recycling.requests")


def log_request(response: ApiResponse, trace: Trace, latency_s: float, provider: str) -> None:
    logger.info(
        json.dumps(
            {
                "request_id": response.request_id,
                "ts": round(time.time(), 3),
                "action": response.action,
                "reason_code": response.reason_code,
                "latency_ms": round(latency_s * 1000),
                "provider": provider,
                "models": sorted(trace.usage.models),
                "llm_calls": trace.usage.calls,
                "prompt_tokens": trace.usage.prompt_tokens,
                "completion_tokens": trace.usage.completion_tokens,
                "router_row": trace.router_row,
                "served_from_cache": response.served_from_cache,
            }
        )
    )


class RateLimiter:
    """In-memory sliding window per client IP (single process, local use)."""

    def __init__(self, per_minute: int) -> None:
        self.per_minute = per_minute
        self._hits: dict[str, deque[float]] = defaultdict(deque)
        self._lock = Lock()

    def allow(self, key: str) -> bool:
        if self.per_minute <= 0:
            return True
        now = time.monotonic()
        with self._lock:
            hits = self._hits[key]
            while hits and now - hits[0] > 60:
                hits.popleft()
            if len(hits) >= self.per_minute:
                return False
            hits.append(now)
            return True
