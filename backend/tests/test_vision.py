import asyncio
import io
import json
from types import SimpleNamespace

import httpx
import openai
import pytest
from PIL import Image

from backend.app.config import load_settings
from backend.app.policy.vision_gate import gate_vision
from backend.app.providers.vision import (
    CachingVisionProvider,
    QwenVisionProvider,
    VisionAlt,
    VisionItem,
    VisionResult,
    VisionUnavailable,
    vision_system_prompt,
)

from .conftest import ScriptedLLM

LABELS = ("PET bottle", "can", "battery", "phone charger")
GOOD = {"answers_question": True, "bin_category": "Plastic", "answer_text": "Beverage plastic bottles go in Plastic.", "used_chunk_ids": ["plastic-do"]}


def item(label: str, conf: float = 0.9, alts: tuple[tuple[str, float], ...] = ()) -> VisionItem:
    return VisionItem(label, label, "unknown", conf, tuple(VisionAlt(a, c) for a, c in alts))


def result(quality: str = "ok", *items: VisionItem) -> VisionResult:
    return VisionResult(image_quality=quality, items=items, model="fake")


def gate(r: VisionResult):
    return gate_vision(r, LABELS, min_conf=0.7, margin=0.15)


# ------------------------------------------------------------------ gate (R7)


@pytest.mark.parametrize(
    "r, key",
    [
        (result("blurry"), "IMAGE_UNREADABLE"),
        (result("dark"), "IMAGE_UNREADABLE"),
        (result("no_waste_item"), "LOW_IMAGE_CONFIDENCE"),
        (result("ok"), "LOW_IMAGE_CONFIDENCE"),
        (result("ok", item("can"), item("PET bottle")), "MULTIPLE_ITEMS"),
        (result("ok", item("other")), "LOW_IMAGE_CONFIDENCE"),
        (result("ok", item("toaster oven")), "LOW_IMAGE_CONFIDENCE"),
        (result("ok", item("can", 0.69)), "LOW_IMAGE_CONFIDENCE"),
        (result("ok", item("can", 0.8, (("PET bottle", 0.7),))), "LOW_IMAGE_CONFIDENCE"),
    ],
)
def test_gate_asks_for_clearer_input(r, key):
    assert gate(r).template_key == key


def test_gate_passes_a_clear_single_item_with_the_canonical_label():
    d = gate(result("ok", item("pet bottle", 0.92, (("can", 0.05), ("pet bottle", 0.9)))))
    assert (d.template_key, d.label, d.confidence) == (None, "PET bottle", 0.92)


# ------------------------------------------------------------ pipeline flow


class FakeVision:
    name = "fake"

    def __init__(self, r: VisionResult | Exception) -> None:
        self.r = r
        self.calls = 0

    def classify(self, image_bytes: bytes, mime: str) -> VisionResult:
        self.calls += 1
        if isinstance(self.r, Exception):
            raise self.r
        return self.r


def photo() -> bytes:
    buf = io.BytesIO()
    Image.new("RGB", (64, 64), "white").save(buf, format="PNG")
    return buf.getvalue()


def ask(make_pipeline, vision, message="", llm=None):
    p = make_pipeline(llm=llm or ScriptedLLM([GOOD]), vision=vision)
    return asyncio.run(p.run(message, image_bytes=photo()))


def test_clear_photo_answers_through_retrieval_and_citation(make_pipeline):
    llm = ScriptedLLM([GOOD])
    out = ask(make_pipeline, FakeVision(result("ok", item("PET bottle", 0.95))), llm=llm)
    r = out.response
    assert (r.action, r.bin_category) == ("answer", "Plastic")
    assert r.citations and r.image is not None
    assert (r.image.item_label, r.image.needs_clearer_input) == ("PET bottle", False)
    assert "intent" not in llm.calls  # no text, so no intent call
    assert out.trace.vision_gate == "pass"


def test_photo_label_goes_through_the_hazardous_route(make_pipeline):
    r = ask(make_pipeline, FakeVision(result("ok", item("battery", 0.95)))).response
    assert (r.action, r.reason_code, r.bin_category) == ("defer", "HAZARDOUS_OFFICIAL_LINKS_ONLY", None)
    assert r.image.item_label == "battery"


def test_photo_label_goes_through_the_unsupported_route(make_pipeline):
    r = ask(make_pipeline, FakeVision(result("ok", item("phone charger", 0.95)))).response
    assert (r.action, r.reason_code, r.bin_category) == ("refuse", "NO_UNIFIED_STANDARD", None)


@pytest.mark.parametrize(
    "r, code",
    [
        (result("blurry"), "IMAGE_UNREADABLE"),
        (result("ok", item("can"), item("battery")), "MULTIPLE_ITEMS"),
        (result("ok", item("can", 0.4)), "LOW_IMAGE_CONFIDENCE"),
    ],
)
def test_unclear_photo_defers_and_never_generates(make_pipeline, r, code):
    llm = ScriptedLLM([GOOD])
    resp = ask(make_pipeline, FakeVision(r), llm=llm).response
    assert (resp.action, resp.reason_code, resp.bin_category) == ("defer", code, None)
    assert resp.image.needs_clearer_input
    assert "answer" not in llm.calls


def test_vision_down_falls_back_to_text_only(make_pipeline):
    r = ask(make_pipeline, FakeVision(VisionUnavailable("all failed"))).response
    assert (r.action, r.reason_code) == ("refuse", "SERVICE_UNAVAILABLE")
    assert r.image.needs_clearer_input


def test_text_is_boundary_checked_before_the_photo(make_pipeline):
    vision = FakeVision(result("ok", item("PET bottle", 0.95)))
    r = ask(make_pipeline, vision, message="I'm in Causeway Bay, where does this go?").response
    assert r.reason_code == "OUT_OF_SCOPE_LOCATION"
    assert vision.calls == 0


# ------------------------------------------------- provider + fallback chain


def _response(content: str) -> SimpleNamespace:
    usage = SimpleNamespace(prompt_tokens=100, completion_tokens=20)
    return SimpleNamespace(choices=[SimpleNamespace(message=SimpleNamespace(content=content))], usage=usage)


class FakeCompletions:
    def __init__(self, script: list) -> None:
        self.script = list(script)
        self.models: list[str] = []
        self.messages: list = []

    def create(self, *, model, messages, **kw):
        self.models.append(model)
        self.messages.append(messages)
        nxt = self.script.pop(0)
        if isinstance(nxt, Exception):
            raise nxt
        return _response(nxt)


def provider(tmp_path, script: list) -> tuple[QwenVisionProvider, FakeCompletions]:
    s = load_settings(
        env_file=tmp_path / "missing.env",
        vision_provider="qwen",
        vision_api_key="test",
        vision_model_primary="primary",
        vision_model_fallback="fallback",
    )
    p = QwenVisionProvider(s, LABELS)
    fake = FakeCompletions(script)
    p._client = SimpleNamespace(chat=SimpleNamespace(completions=fake))  # type: ignore[assignment]
    return p, fake


OK_JSON = json.dumps({"image_quality": "ok", "items": [{"label": "Can", "free_text_name": "soda can", "material_guess": "aluminium", "confidence": 0.9}]})
TIMEOUT = openai.APITimeoutError(request=httpx.Request("POST", "https://example.org"))


def test_provider_sends_instruction_then_image_and_parses(tmp_path):
    p, fake = provider(tmp_path, [OK_JSON])
    r = p.classify(b"jpegbytes", "image/jpeg")
    assert (r.model, r.items[0].label, r.items[0].material_guess, r.calls) == ("primary", "can", "unknown", 1)
    user = fake.messages[0][1]["content"]
    assert [part["type"] for part in user] == ["text", "image_url"]
    assert user[1]["image_url"]["url"].startswith("data:image/jpeg;base64,")


def test_unusable_output_is_retried_once_then_falls_back(tmp_path):
    p, fake = provider(tmp_path, ["not json", '{"image_quality": "great"}', OK_JSON])
    r = p.classify(b"x", "image/jpeg")
    assert fake.models == ["primary", "primary", "fallback"]
    assert r.model == "fallback" and r.calls == 3 and len(r.errors) == 2


def test_provider_error_moves_to_fallback_then_gives_up(tmp_path):
    p, fake = provider(tmp_path, [TIMEOUT, TIMEOUT])
    with pytest.raises(VisionUnavailable):
        p.classify(b"x", "image/jpeg")
    assert fake.models == ["primary", "fallback"]


def test_prompt_lists_the_closed_labels():
    prompt = vision_system_prompt(LABELS)
    assert "- phone charger" in prompt and "{LABELS}" not in prompt


def test_eval_cache_stores_hash_and_labels_not_the_image(tmp_path):
    p, fake = provider(tmp_path, [OK_JSON])
    path = tmp_path / "vision_cache.json"
    cached = CachingVisionProvider(p, path)
    first = cached.classify(b"secret-image-bytes", "image/jpeg")
    second = cached.classify(b"secret-image-bytes", "image/jpeg")
    assert len(fake.models) == 1 and second.cached and second.calls == 0
    assert second.items == first.items
    assert "secret-image-bytes" not in path.read_text(encoding="utf-8")
