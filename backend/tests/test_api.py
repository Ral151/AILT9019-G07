import io

import pytest

from backend.app import create_app

from .conftest import ScriptedLLM

GOOD = {"answers_question": True, "bin_category": "Plastic", "answer_text": "Beverage plastic bottles go in Plastic.", "used_chunk_ids": ["plastic-do"]}


class _Store:
    corpus_version = "test"
    chunks: dict = {}


@pytest.fixture
def client(make_pipeline):
    pipeline = make_pipeline(llm=ScriptedLLM([GOOD] * 5))
    app = create_app(settings=pipeline.deps.settings, deps=pipeline.deps, store=_Store())
    app.config["TESTING"] = True
    return app.test_client()


def test_ask_multipart_returns_contract(client):
    resp = client.post("/api/ask", data={"message": "Where does a plastic bottle go?"}, content_type="multipart/form-data")
    assert resp.status_code == 200
    body = resp.get_json()
    assert set(body) == {
        "request_id", "action", "reason_code", "answer_text", "bin_category", "caveats",
        "citations", "redirect", "image", "served_from_cache",
    }
    assert body["bin_category"] == "Plastic"
    assert set(body["citations"][0]) >= {"source_id", "title", "section", "lines", "excerpt", "url"}


def test_ask_rejects_long_and_empty_messages(client):
    assert client.post("/api/ask", data={"message": "x" * 501}).status_code == 400
    assert client.post("/api/ask", data={"message": "  "}).status_code == 400


def test_ask_rejects_oversized_image(client):
    big = io.BytesIO(b"\xff\xd8\xff" + b"0" * (5 * 1024 * 1024 + 10))
    resp = client.post("/api/ask", data={"message": "", "image": (big, "x.jpg")}, content_type="multipart/form-data")
    assert resp.status_code == 413


def test_samples_and_health(client):
    samples = client.get("/api/samples").get_json()["samples"]
    assert "Where do I put an old phone charger?" in samples
    health = client.get("/api/health").get_json()
    assert health["status"] == "ok" and health["vision_enabled"] is False


def test_rate_limit(make_pipeline):
    pipeline = make_pipeline(llm=None)
    settings = pipeline.deps.settings.__class__(**{**pipeline.deps.settings.__dict__, "rate_limit_per_min": 2})
    app = create_app(settings=settings, deps=pipeline.deps, store=_Store())
    c = app.test_client()
    codes = [c.post("/api/ask", data={"message": "Where do I put an old phone charger?"}).status_code for _ in range(3)]
    assert codes == [200, 200, 429]
