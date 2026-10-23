"""Text LLM providers.

`OpenAICompatibleLLM` calls a live provider through the OpenAI
chat-completions API: OpenRouter (default) or Qwen on Alibaba Cloud Model
Studio. `MockTextLLM` is deterministic and exists only for unit tests and for
checking pipeline plumbing without an API key; it is never selected unless
TEXT_PROVIDER=mock.
"""

from __future__ import annotations

import hashlib
import json
import threading
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Protocol

from ..config import LIVE_PROVIDERS, Settings


class ProviderError(RuntimeError):
    """The provider failed (timeout, quota, 4xx/5xx, unreadable output)."""


@dataclass(frozen=True)
class LLMResult:
    data: dict[str, Any]
    model: str
    prompt_tokens: int = 0
    completion_tokens: int = 0
    cached: bool = False


@dataclass
class UsageTotals:
    calls: int = 0
    prompt_tokens: int = 0
    completion_tokens: int = 0
    models: set[str] = field(default_factory=set)

    def add(self, result: LLMResult) -> None:
        self.calls += 1
        self.prompt_tokens += result.prompt_tokens
        self.completion_tokens += result.completion_tokens
        self.models.add(result.model)


class TextLLM(Protocol):
    name: str

    def complete_json(
        self, *, task: str, model: str, system: str, user: str, context: dict[str, Any]
    ) -> LLMResult:
        """Return the parsed JSON object. `context` is only used by the mock."""
        ...


def _parse_json(text: str) -> dict[str, Any]:
    text = text.strip()
    if text.startswith("```"):
        text = text.lstrip("`").lstrip()  # drop a ```json / ``` fence
    decoder = json.JSONDecoder()
    idx = text.find("{")
    while idx != -1:
        try:
            value, _ = decoder.raw_decode(text[idx:])
        except json.JSONDecodeError:
            # This '{' opened something malformed/truncated; try the next one.
            idx = text.find("{", idx + 1)
            continue
        if isinstance(value, dict):
            return value
        # Decoded, but it wasn't an object (e.g. a list); keep looking.
        idx = text.find("{", idx + 1)
    raise ProviderError("model output contained no valid JSON object")


# Provider-specific request fields that keep reasoning/thinking off, for
# latency and so the whole max_tokens budget goes to the JSON answer.
REASONING_OFF: dict[str, dict[str, Any]] = {
    # OpenRouter unified reasoning parameter; "none" disables it on models
    # where reasoning is not mandatory (checked for the default model).
    "openrouter": {"reasoning": {"effort": "none"}},
    # Qwen3 hybrid models; JSON mode also requires thinking off.
    "qwen": {"enable_thinking": False},
}


class OpenAICompatibleLLM:
    def __init__(self, settings: Settings) -> None:
        from openai import OpenAI

        self.name = settings.text_provider
        self._extra_body = REASONING_OFF.get(settings.text_provider, {})
        self._client = OpenAI(
            api_key=settings.llm_api_key,
            base_url=settings.llm_base_url,
            timeout=settings.provider_timeout_s,
            max_retries=2,  # SDK retries 429/5xx/timeouts with backoff
        )

    def complete_json(
        self, *, task: str, model: str, system: str, user: str, context: dict[str, Any]
    ) -> LLMResult:
        import openai

        try:
            resp = self._client.chat.completions.create(
                model=model,
                messages=[{"role": "system", "content": system}, {"role": "user", "content": user}],
                temperature=0,
                max_tokens=400,
                response_format={"type": "json_object"},
                extra_body=self._extra_body,
            )
        except openai.APIStatusError as exc:
            # e.g. 429 rate limit (OpenRouter free-model caps), 402 no credit,
            # 403 AllocationQuota.FreeTierOnly (Qwen), 5xx.
            raise ProviderError(f"{task}: provider returned HTTP {exc.status_code}") from exc
        except openai.OpenAIError as exc:  # timeouts, connection errors
            raise ProviderError(f"{task}: {type(exc).__name__}") from exc
        if not resp.choices or not resp.choices[0].message.content:
            reason = resp.choices[0].finish_reason if resp.choices else "no choices"
            raise ProviderError(f"{task}: empty response (finish_reason={reason})")
        usage = resp.usage
        return LLMResult(
            data=_parse_json(resp.choices[0].message.content),
            model=resp.model or model,
            prompt_tokens=getattr(usage, "prompt_tokens", 0) or 0,
            completion_tokens=getattr(usage, "completion_tokens", 0) or 0,
        )

    def ping(self) -> bool:
        try:
            self._client.models.list()
            return True
        except Exception:
            return False


class MockTextLLM:
    """Deterministic stand-in. Never used for real answers or evaluation scores."""

    name = "mock"

    def complete_json(
        self, *, task: str, model: str, system: str, user: str, context: dict[str, Any]
    ) -> LLMResult:
        if task == "intent":
            data: dict[str, Any] = {"intent": "recycling_question", "items": [], "mentions_location_outside_hku": False}
        elif task == "answer":
            excerpts: list[dict[str, Any]] = context["excerpts"]
            with_stream = [e for e in excerpts if e.get("stream")]
            chosen = with_stream[0] if with_stream else excerpts[0]
            stream = chosen.get("stream")
            text = (
                f"The official guide lists this under {stream}."
                if stream
                else "The official guide covers this in the quoted excerpt."
            )
            data = {
                "answers_question": True,
                "bin_category": stream,
                "answer_text": text,
                "used_chunk_ids": [chosen["id"]],
            }
        else:
            raise ProviderError(f"mock has no task {task!r}")
        return LLMResult(data=data, model="mock")


class CachingTextLLM:
    """Caches outputs on disk keyed by (task, model, prompt hash). Eval only,
    so re-scoring a run does not spend free quota (§7.5)."""

    def __init__(self, inner: TextLLM, path: Path) -> None:
        self.inner = inner
        self.name = f"{inner.name}+cache"
        self.path = path
        self._lock = threading.Lock()
        self._cache: dict[str, dict[str, Any]] = (
            json.loads(path.read_text(encoding="utf-8")) if path.exists() else {}
        )

    def complete_json(
        self, *, task: str, model: str, system: str, user: str, context: dict[str, Any]
    ) -> LLMResult:
        key = hashlib.sha256(f"{task}\0{model}\0{system}\0{user}".encode("utf-8")).hexdigest()
        with self._lock:
            hit = self._cache.get(key)
        if hit is not None:
            return LLMResult(data=hit["data"], model=hit["model"], cached=True)
        result = self.inner.complete_json(task=task, model=model, system=system, user=user, context=context)
        with self._lock:
            self._cache[key] = {"data": result.data, "model": result.model}
            self.path.parent.mkdir(parents=True, exist_ok=True)
            self.path.write_text(json.dumps(self._cache, indent=1, sort_keys=True), encoding="utf-8")
        return result


def build_text_llm(settings: Settings) -> TextLLM | None:
    llm: TextLLM | None
    if settings.text_provider in LIVE_PROVIDERS and settings.llm_api_key:
        llm = OpenAICompatibleLLM(settings)
    elif settings.text_provider == "mock":
        llm = MockTextLLM()
    else:
        return None
    if settings.llm_cache_path is not None:
        llm = CachingTextLLM(llm, settings.llm_cache_path)
    return llm
