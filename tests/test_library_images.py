import hashlib
import math

import pytest
from fastapi.testclient import TestClient

from jarvis import google_ai, images, library
from jarvis.brain import Brain
from jarvis.server import create_app
from jarvis.tools import REGISTRY, ToolError, available_tools, load_all
from tests.conftest import FakeClaude, response, text, tool_use

LEASE = ("Tenancy contract for Apartment 1204, Marina Heights.\n\n" + "General terms apply. " * 60 +
         "\n\nNotice period: either party must give 90 days written notice before the end of the lease.\n\n"
         + "Maintenance is the landlord's duty. " * 40 + "\n\nAnnual rent: 95,000 AED in 4 cheques.")


def fake_embed(settings, texts, query=False):
    """Bag-of-words vectors: texts sharing words point the same way."""
    out = []
    for t in texts:
        vec = [0.0] * 64
        for word in t.lower().split():
            word = word.strip(".,:;!?")
            if len(word) > 3:
                vec[int(hashlib.md5(word.encode()).hexdigest(), 16) % 64] += 1
        out.append(vec)
    return out


@pytest.fixture
def gem(ctx, monkeypatch):
    ctx.settings.gemini_api_key = "test"
    monkeypatch.setattr(google_ai, "embed", fake_embed)
    library._vector_cache.clear()
    return ctx


def run(ctx, tool_name, **args):
    load_all()
    return REGISTRY[tool_name].handler(ctx, args)


# ------------------------------------------------------------------ library
def test_chunking_overlaps_and_prefers_breaks():
    pieces = library.chunk(LEASE)
    assert len(pieces) >= 3 and all(len(p) <= library.CHUNK_CHARS for p in pieces)
    assert "".join(pieces).count("Notice period") >= 1
    assert library.chunk("") == [] and library.chunk("short") == ["short"]


def test_semantic_search(gem):
    doc = library.add_document(gem, "Lease.pdf", LEASE)
    library.add_document(gem, "Pizza menu.txt", "Margherita pizza 35 AED. Pepperoni pizza 42 AED. Garlic bread.")
    hits = library.search(gem, "what notice period does the lease need")
    assert hits[0]["doc_id"] == doc and "90 days written notice" in hits[0]["text"] and hits[0]["name"] == "Lease.pdf"
    out = run(gem, "search_library", query="pepperoni pizza price")
    assert out.startswith("[#2 Pizza menu.txt") and "42 AED" in out
    assert "#1 Lease.pdf" in run(gem, "list_library")


def test_keyword_fallback_without_gemini(ctx):
    library.add_document(ctx, "Lease.pdf", LEASE)
    assert ctx.db.one("SELECT COUNT(*) AS n FROM chunks WHERE embedding IS NULL")["n"] > 0
    hits = library.search(ctx, "notice period")
    assert hits and "90 days" in hits[0]["text"]
    assert library.search(ctx, "zebra") == []


def test_backfill_embeds_later(ctx, monkeypatch):
    library.add_document(ctx, "Lease.pdf", LEASE)  # no key yet: stored without vectors
    ctx.settings.gemini_api_key = "test"
    monkeypatch.setattr(google_ai, "embed", fake_embed)
    library._vector_cache.clear()
    assert "90 days" in library.search(ctx, "lease notice period")[0]["text"]
    assert ctx.db.one("SELECT COUNT(*) AS n FROM chunks WHERE embedding IS NULL")["n"] == 0


def test_attachments_are_saved_to_the_library(gem):
    claude = FakeClaude(response(text("It's your lease.")))
    Brain(gem, client=claude).chat("what's this?", attachment=("lease.txt", LEASE.encode(), "text/plain"))
    assert library.documents(gem)[0]["name"] == "lease.txt"
    assert "Saved to the user's library as document #1" in claude.requests[0]["messages"][-1]["content"][-1]["text"]
    assert run(gem, "forget_document", id=1).startswith("Removed")
    assert gem.db.one("SELECT COUNT(*) AS n FROM chunks")["n"] == 0
    with pytest.raises(ToolError):
        run(gem, "forget_document", id=1)


def test_save_webpage(gem, monkeypatch):
    monkeypatch.setattr("jarvis.tools.extras.fetch_page", lambda url: ("https://blog.example/post", "Great post", "Body " * 50))
    assert run(gem, "save_webpage", url="blog.example/post") == 'Saved "Great post" to the library as document #1.'
    assert library.documents(gem)[0]["source"] == "https://blog.example/post"


def test_library_endpoints(gem):
    library.add_document(gem, "Lease.pdf", LEASE)
    app = create_app(gem, brain_factory=lambda **kw: Brain(gem, client=FakeClaude(), **kw))
    client = TestClient(app, base_url="http://localhost", client=("127.0.0.1", 5000))
    rows = client.get("/api/list/library").json()
    assert rows[0]["title"] == "Lease.pdf" and rows[0]["chars"] == len(LEASE)
    assert client.get("/api/dashboard").json()["counts"]["library"] == 1
    assert client.get("/api/export").json()["library"][0]["name"] == "Lease.pdf"
    assert client.post("/api/library/1/delete").json() == {"ok": True}
    assert client.post("/api/library/1/delete").status_code == 404


# ------------------------------------------------------------------ pictures
PNG = b"\x89PNG\r\n\x1a\nfake-picture"


def test_picture_tool_only_with_gemini(ctx):
    assert "generate_image" not in {t.name for t in available_tools(ctx.settings)}
    ctx.settings.gemini_api_key = "test"
    assert "generate_image" in {t.name for t in available_tools(ctx.settings)}


def test_pictures_in_chat(gem, monkeypatch):
    calls = []

    def fake_generate(settings, prompt, source=None):
        calls.append((prompt, source))
        return PNG, "image/png", ""

    monkeypatch.setattr(google_ai, "generate_image", fake_generate)
    claude = FakeClaude(
        response(tool_use("generate_image", {"prompt": "A falcon over Dubai at sunset"})),
        response(text("Here's your falcon.")),
        response(tool_use("generate_image", {"prompt": "Make it night", "edit_last": True})),
        response(text("Now at night.")),
    )
    app = create_app(gem, brain_factory=lambda **kw: Brain(gem, client=claude, **kw))
    client = TestClient(app, base_url="http://localhost", client=("127.0.0.1", 5000))
    first = client.post("/api/chat", json={"text": "draw a falcon"}).json()
    assert first["reply"] == "Here's your falcon." and first["images"] == [1]
    pic = client.get("/api/images/1")
    assert pic.content == PNG and pic.headers["content-type"] == "image/png"
    second = client.post("/api/chat", json={"text": "make it night"}).json()
    assert second["images"] == [2] and calls[1] == ("Make it night", (PNG, "image/png"))
    assert client.get("/api/usage").json()["today"]["images"] == 2
    gem.settings.access_token = "tok"
    assert client.get("/api/images/1").status_code == 401
    assert client.get("/api/images/99", headers={"Authorization": "Bearer tok"}).status_code == 404


def test_edit_needs_a_recent_picture(gem):
    images._last.clear()
    with pytest.raises(ToolError, match="no recent picture"):
        run(gem, "generate_image", prompt="make it blue", edit_last=True)


def test_only_the_newest_pictures_are_kept(ctx):
    for i in range(images.KEEP + 5):
        images.save(ctx, f"p{i}", PNG, "image/png")
    ids = [r["id"] for r in ctx.db.query("SELECT id FROM images ORDER BY id")]
    assert len(ids) == images.KEEP and ids[0] == 6 and images.get(ctx, 1) is None


def test_picture_model_is_discovered(ctx, monkeypatch):
    from types import SimpleNamespace

    google_ai._image_model.clear()
    ctx.settings.gemini_api_key = "k-discover"
    models = [SimpleNamespace(name=n, supported_actions=["generateContent"]) for n in (
        "models/gemini-3.8-flash", "models/gemini-2.5-flash-image", "models/gemini-3.1-flash-image",
        "models/gemini-3.5-flash-image-preview", "models/imagen-4")]
    monkeypatch.setattr(google_ai, "client", lambda s: SimpleNamespace(models=SimpleNamespace(list=lambda: models)))
    assert google_ai.image_model(ctx.settings) == "gemini-3.1-flash-image"
    monkeypatch.setenv("IMAGE_MODEL", "my-model")
    assert google_ai.image_model(ctx.settings) == "my-model"


def test_generate_image_reads_the_picture_part(ctx, monkeypatch):
    from google.genai import types

    ctx.settings.gemini_api_key = "k"
    monkeypatch.setenv("IMAGE_MODEL", "img")
    reply = types.GenerateContentResponse.model_validate({"candidates": [{"content": {"role": "model", "parts": [
        {"text": "Here you go"}, {"inline_data": {"mime_type": "image/png", "data": PNG}}]}}]})
    seen = {}

    def generate_content(model, contents, config):
        seen.update(model=model, modalities=config.response_modalities)
        return reply

    from types import SimpleNamespace

    monkeypatch.setattr(google_ai, "client", lambda s: SimpleNamespace(models=SimpleNamespace(generate_content=generate_content)))
    assert google_ai.generate_image(ctx.settings, "a cat") == (PNG, "image/png", "Here you go")
    assert seen == {"model": "img", "modalities": ["IMAGE", "TEXT"]}
    blocked = types.GenerateContentResponse.model_validate({"candidates": [{"content": {"role": "model", "parts": [{"text": "I can't draw that."}]}}]})
    monkeypatch.setattr(google_ai, "client", lambda s: SimpleNamespace(models=SimpleNamespace(generate_content=lambda **kw: blocked)))
    with pytest.raises(google_ai.AIUnavailable, match="I can't draw that"):
        google_ai.generate_image(ctx.settings, "x")
