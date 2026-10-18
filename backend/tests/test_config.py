import pytest

from backend.app.config import load_settings
from backend.app.providers.llm import OpenAICompatibleLLM, build_text_llm

ENV_VARS = (
    "TEXT_PROVIDER", "TEXT_MODEL", "INTENT_MODEL",
    "OPENROUTER_API_KEY", "OPENROUTER_BASE_URL", "QWEN_API_KEY", "QWEN_BASE_URL",
)


@pytest.fixture
def env(monkeypatch, tmp_path):
    for name in ENV_VARS:
        monkeypatch.delenv(name, raising=False)

    def _load(**values):
        for k, v in values.items():
            monkeypatch.setenv(k, v)
        return load_settings(env_file=tmp_path / "missing.env")

    return _load


def test_no_key_is_safe_mode(env):
    s = env()
    assert s.text_provider == "none"
    assert s.llm_api_key is None
    assert build_text_llm(s) is None


def test_openrouter_key_selects_openrouter_defaults(env):
    s = env(OPENROUTER_API_KEY="sk-or-test")
    assert s.text_provider == "openrouter"
    assert s.llm_base_url == "https://openrouter.ai/api/v1"
    assert s.text_model == s.intent_model == "nvidia/nemotron-3.5-super-vl:free"


def test_qwen_key_selects_qwen_defaults(env):
    s = env(QWEN_API_KEY="sk-qwen-test")
    assert s.text_provider == "qwen"
    assert "dashscope" in s.llm_base_url
    assert s.text_model == "qwen-plus"


def test_openrouter_wins_when_both_keys_set(env):
    assert env(OPENROUTER_API_KEY="a", QWEN_API_KEY="b").text_provider == "openrouter"


def test_explicit_provider_and_model_override(env):
    s = env(OPENROUTER_API_KEY="a", QWEN_API_KEY="b", TEXT_PROVIDER="qwen", TEXT_MODEL="qwen-max", INTENT_MODEL="qwen-flash")
    assert s.text_provider == "qwen"
    assert s.llm_api_key == "b"
    assert (s.text_model, s.intent_model) == ("qwen-max", "qwen-flash")


def test_explicit_provider_without_its_key_is_safe_mode(env):
    assert env(QWEN_API_KEY="b", TEXT_PROVIDER="openrouter").text_provider == "none"


@pytest.mark.parametrize(
    ("key_env", "expected"),
    [
        ("OPENROUTER_API_KEY", {"reasoning": {"effort": "none"}}),
        ("QWEN_API_KEY", {"enable_thinking": False}),
    ],
)
def test_reasoning_is_switched_off_per_provider(env, key_env, expected):
    llm = build_text_llm(env(**{key_env: "test"}))
    assert isinstance(llm, OpenAICompatibleLLM)
    assert llm._extra_body == expected
