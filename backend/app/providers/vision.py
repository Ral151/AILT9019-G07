"""Vision providers (§7). The model only names the item (R6); the bin comes
from retrieval + citation exactly as for text, and the R7 confidence gate is
deterministic code (`policy.vision_gate`).

`QwenVisionProvider` calls Qwen on Model Studio (OpenAI-compatible) and walks
the fallback chain primary -> fallback (§7.6). When every model fails it
raises `VisionUnavailable`, and the pipeline asks the user to describe the
item in words. Image bytes stay in memory (R8): they are sent to the provider
and never written, logged or cached.
"""

from __future__ import annotations

import base64
import hashlib
import json
import threading
from collections.abc import Sequence
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any, Protocol

from pydantic import ValidationError

from ..config import Settings
from ..prompts import VISION_PROMPT, load_prompt
from ..schemas import VisionOutput
from .llm import REASONING_OFF, ProviderError, _parse_json

MAX_VISION_ATTEMPTS = 2  # per model: first try + one retry on unusable output (§7.3)


@dataclass(frozen=True)
class VisionAlt:
    label: str
    confidence: float


@dataclass(frozen=True)
class VisionItem:
    label: str
    free_text_name: str
    material_guess: str
    confidence: float
    alternatives: tuple[VisionAlt, ...] = ()


@dataclass(frozen=True)
class VisionResult:
    image_quality: str  # ok | blurry | dark | no_waste_item
    items: tuple[VisionItem, ...]
    model: str
    calls: int = 1
    prompt_tokens: int = 0
    completion_tokens: int = 0
    errors: tuple[str, ...] = field(default=())
    cached: bool = False

    @classmethod
    def from_output(cls, out: VisionOutput, **kwargs: Any) -> "VisionResult":
        items = tuple(
            VisionItem(
                label=i.label,
                free_text_name=i.free_text_name,
                material_guess=i.material_guess,
                confidence=i.confidence,
                alternatives=tuple(VisionAlt(a.label.casefold(), a.confidence) for a in i.alternatives),
            )
            for i in out.items
        )
        return cls(image_quality=out.image_quality, items=items, **kwargs)

    @classmethod
    def from_dict(cls, d: dict[str, Any]) -> "VisionResult":
        items = tuple(
            VisionItem(**{**i, "alternatives": tuple(VisionAlt(**a) for a in i["alternatives"])}) for i in d["items"]
        )
        return cls(**{**d, "items": items, "errors": tuple(d.get("errors", ()))})


class VisionUnavailable(RuntimeError):
    """Every model in the chain failed; the caller falls back to text-only."""


class VisionProvider(Protocol):
    name: str

    def classify(self, image_bytes: bytes, mime: str) -> VisionResult: ...


class UnavailableVisionProvider:
    """No vision provider configured: every photo gets the text-only message."""

    name = "none"

    def classify(self, image_bytes: bytes, mime: str) -> VisionResult:
        raise VisionUnavailable("no vision provider configured")


def vision_system_prompt(labels: Sequence[str]) -> str:
    return load_prompt(VISION_PROMPT).replace("{LABELS}", "\n".join(f"- {label}" for label in labels))


class QwenVisionProvider:
    name = "qwen"

    def __init__(self, settings: Settings, labels: Sequence[str]) -> None:
        from openai import OpenAI

        self.models = [m for m in dict.fromkeys([settings.vision_model_primary, settings.vision_model_fallback]) if m]
        self._system = vision_system_prompt(labels)
        self._client = OpenAI(
            api_key=settings.vision_api_key,
            base_url=settings.vision_base_url,
            timeout=settings.provider_timeout_s,
            max_retries=0,  # the fallback model is the retry; keeps the worst case at 4 calls
        )

    def _call(self, model: str, data_url: str) -> tuple[str, int, int]:
        import openai

        try:
            resp = self._client.chat.completions.create(
                model=model,
                messages=[
                    {"role": "system", "content": self._system},
                    {
                        "role": "user",
                        "content": [  # instruction text first, then the image (§7.3)
                            {"type": "text", "text": "Identify the waste item(s) in this photo."},
                            {"type": "image_url", "image_url": {"url": data_url}},
                        ],
                    },
                ],
                temperature=0,
                max_tokens=400,
                response_format={"type": "json_object"},
                extra_body=REASONING_OFF["qwen"],
            )
        except openai.APIStatusError as exc:
            # 429 rate limit, 401/403 key or quota, 5xx.
            raise ProviderError(f"vision {model}: provider returned HTTP {exc.status_code}") from exc
        except openai.OpenAIError as exc:  # timeouts, connection errors
            raise ProviderError(f"vision {model}: {type(exc).__name__}") from exc
        if not resp.choices or not resp.choices[0].message.content:
            raise ProviderError(f"vision {model}: empty response")
        usage = resp.usage
        return (
            resp.choices[0].message.content,
            getattr(usage, "prompt_tokens", 0) or 0,
            getattr(usage, "completion_tokens", 0) or 0,
        )

    def classify(self, image_bytes: bytes, mime: str) -> VisionResult:
        data_url = f"data:{mime};base64," + base64.b64encode(image_bytes).decode("ascii")
        errors: list[str] = []
        calls = prompt_tokens = completion_tokens = 0
        for model in self.models:
            for _ in range(MAX_VISION_ATTEMPTS):
                calls += 1
                try:
                    content, p_tok, c_tok = self._call(model, data_url)
                except ProviderError as exc:
                    errors.append(str(exc))
                    break  # provider failure: go to the next model
                prompt_tokens += p_tok
                completion_tokens += c_tok
                # Unusable output: retry once on the same model, then move on.
                try:
                    out = VisionOutput.model_validate(_parse_json(content))
                except ProviderError:
                    errors.append(f"vision {model}: no JSON object in output")
                    continue
                except ValidationError as exc:
                    errors.append(f"vision {model}: {exc.error_count()} schema error(s)")
                    continue
                return VisionResult.from_output(
                    out,
                    model=model,
                    calls=calls,
                    prompt_tokens=prompt_tokens,
                    completion_tokens=completion_tokens,
                    errors=tuple(errors),
                )
        raise VisionUnavailable("; ".join(errors) or "no vision model configured")


class CachingVisionProvider:
    """Eval only: caches results keyed by (image hash, prompt, models), so
    re-scoring a run does not spend quota. Stores the SHA-256 of the photo and
    the model's label output, never the image itself (R8)."""

    def __init__(self, inner: QwenVisionProvider, path: Path) -> None:
        self.inner = inner
        self.name = f"{inner.name}+cache"
        self.path = path
        self._lock = threading.Lock()
        self._cache: dict[str, dict[str, Any]] = (
            json.loads(path.read_text(encoding="utf-8")) if path.exists() else {}
        )

    def classify(self, image_bytes: bytes, mime: str) -> VisionResult:
        digest = hashlib.sha256(image_bytes).hexdigest()
        key = hashlib.sha256(f"{digest}\0{self.inner._system}\0{','.join(self.inner.models)}".encode()).hexdigest()
        with self._lock:
            hit = self._cache.get(key)
        if hit is not None:
            return VisionResult.from_dict(
                {**hit, "cached": True, "calls": 0, "prompt_tokens": 0, "completion_tokens": 0}
            )
        result = self.inner.classify(image_bytes, mime)  # VisionUnavailable is not cached
        with self._lock:
            self._cache[key] = asdict(result)
            self.path.parent.mkdir(parents=True, exist_ok=True)
            self.path.write_text(json.dumps(self._cache, indent=1, sort_keys=True), encoding="utf-8")
        return result


def build_vision_provider(settings: Settings, labels: Sequence[str]) -> VisionProvider:
    if not settings.vision_enabled:
        return UnavailableVisionProvider()
    provider = QwenVisionProvider(settings, labels)
    if settings.vision_cache_path is not None:
        return CachingVisionProvider(provider, settings.vision_cache_path)
    return provider
