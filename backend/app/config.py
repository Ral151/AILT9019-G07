"""Runtime settings, read once from the environment (and `.env` if present).

Secrets (API keys) only ever come from the environment. Nothing here is an
HKU rule: rules, bin categories and locations come from `corpus/`.
"""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from pathlib import Path

from dotenv import load_dotenv

REPO_ROOT = Path(__file__).resolve().parents[2]

# Calibrated on the dev split with `python -m eval.calibrate_tau --split dev`.
# See eval/reports/tau_calibration.md. Override with RETRIEVE_TAU.
DEFAULT_RETRIEVE_TAU = 0.688

# Live text providers. Both speak the OpenAI chat-completions API; each has its
# own key, base URL and default model. TEXT_MODEL / INTENT_MODEL override the
# default model, and <PROVIDER>_BASE_URL overrides the base URL.
PROVIDER_DEFAULTS: dict[str, dict[str, str]] = {
    "openrouter": {
        "key_env": "OPENROUTER_API_KEY",
        "url_env": "OPENROUTER_BASE_URL",
        "base_url": "https://openrouter.ai/api/v1",
        "model": "nvidia/nemotron-3.5-super-vl:free",
    },
    "qwen": {
        "key_env": "QWEN_API_KEY",
        "url_env": "QWEN_BASE_URL",
        "base_url": "https://dashscope-intl.aliyuncs.com/compatible-mode/v1",
        "model": "qwen-plus",
    },
}
LIVE_PROVIDERS = tuple(PROVIDER_DEFAULTS)


def _env(name: str, default: str | None = None) -> str | None:
    value = os.environ.get(name)
    if value is None or value.strip() == "":
        return default
    return value.strip()


def _env_float(name: str, default: float) -> float:
    raw = _env(name)
    return float(raw) if raw is not None else default


def _env_int(name: str, default: int) -> int:
    raw = _env(name)
    return int(raw) if raw is not None else default


@dataclass(frozen=True)
class Settings:
    # Text LLM (OpenAI-compatible: OpenRouter or Qwen on Model Studio).
    # text_provider: "openrouter" | "qwen" (live), "mock" (deterministic,
    # tests/plumbing only) or "none".
    text_provider: str
    llm_api_key: str | None
    llm_base_url: str
    text_model: str
    intent_model: str
    # Vision (milestone M4); recorded here so /api/health can report it.
    vision_model_primary: str
    vision_model_fallback: str

    # Retrieval.
    chroma_path: Path
    chroma_collection: str
    embed_model: str
    retrieve_tau: float
    retrieve_top_k: int = 5
    max_selected_chunks: int = 3

    # Request handling.
    provider_timeout_s: float = 15.0
    max_message_chars: int = 500
    max_image_bytes: int = 5 * 1024 * 1024
    max_image_pixels: int = 40_000_000
    image_max_edge: int = 1024
    rate_limit_per_min: int = 20
    cors_origins: tuple[str, ...] = field(default_factory=tuple)

    # Demo cache (FR-10): "on" serves reviewed cached answers for sample
    # questions; "auto" only does so when the provider fails; "off" never.
    demo_cache: str = "auto"
    demo_cache_path: Path = REPO_ROOT / "backend" / "app" / "demo_cache.json"

    # Eval harness: cache LLM outputs keyed by (prompt hash, model).
    llm_cache_path: Path | None = None

    @property
    def llm_enabled(self) -> bool:
        return self.text_provider in (*LIVE_PROVIDERS, "mock")


def _resolve_provider() -> str:
    """TEXT_PROVIDER if set; otherwise the first live provider whose API key
    is present (OpenRouter first), else "none". A live provider without its
    key falls back to "none" (safe mode)."""
    explicit = (_env("TEXT_PROVIDER") or "").lower()
    if explicit:
        if explicit in LIVE_PROVIDERS and not _env(PROVIDER_DEFAULTS[explicit]["key_env"]):
            return "none"
        return explicit
    for name in LIVE_PROVIDERS:
        if _env(PROVIDER_DEFAULTS[name]["key_env"]):
            return name
    return "none"


def load_settings(env_file: Path | None = None, **overrides: object) -> Settings:
    load_dotenv(env_file or REPO_ROOT / ".env", override=False)

    provider = _resolve_provider()
    defaults = PROVIDER_DEFAULTS.get(provider, PROVIDER_DEFAULTS["openrouter"])
    api_key = _env(defaults["key_env"]) if provider in LIVE_PROVIDERS else None
    text_model = _env("TEXT_MODEL", defaults["model"]) or defaults["model"]

    cors = tuple(o.strip() for o in (_env("CORS_ORIGINS", "") or "").split(",") if o.strip())
    chroma_path = Path(_env("CHROMA_PATH", str(REPO_ROOT / "data" / "chroma")) or "")
    if not chroma_path.is_absolute():
        chroma_path = REPO_ROOT / chroma_path

    values: dict[str, object] = dict(
        text_provider=provider,
        llm_api_key=api_key,
        llm_base_url=_env(defaults["url_env"], defaults["base_url"]) or defaults["base_url"],
        text_model=text_model,
        intent_model=_env("INTENT_MODEL", text_model) or text_model,
        vision_model_primary=_env("VISION_MODEL_PRIMARY", "qwen3-vl-plus") or "qwen3-vl-plus",
        vision_model_fallback=_env("VISION_MODEL_FALLBACK", "qwen3-vl-flash") or "qwen3-vl-flash",
        chroma_path=chroma_path,
        chroma_collection=_env("CHROMA_COLLECTION", "hku_recycling") or "hku_recycling",
        embed_model=_env("EMBED_MODEL", "BAAI/bge-small-en-v1.5") or "BAAI/bge-small-en-v1.5",
        retrieve_tau=_env_float("RETRIEVE_TAU", DEFAULT_RETRIEVE_TAU),
        provider_timeout_s=_env_float("PROVIDER_TIMEOUT_S", 15.0),
        rate_limit_per_min=_env_int("RATE_LIMIT", 20),
        cors_origins=cors,
        demo_cache=(_env("DEMO_CACHE", "auto") or "auto").lower(),
    )
    values.update(overrides)
    return Settings(**values)  # type: ignore[arg-type]
