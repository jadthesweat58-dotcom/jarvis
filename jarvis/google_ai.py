"""Gemini services beyond chat: text embeddings (for the library search) and
picture generation. They use GEMINI_API_KEY whichever brain answers the chat.
"""

from __future__ import annotations

import logging
import os
import threading
from typing import Any

log = logging.getLogger("jarvis.google_ai")

EMBED_DIMENSIONS = 768
EMBED_BATCH = 50
_clients: dict[str, Any] = {}
_image_model: dict[str, str] = {}
_lock = threading.Lock()


class AIUnavailable(RuntimeError):
    pass


def client(settings: Any) -> Any:
    key = settings.gemini_api_key
    if not key:
        raise AIUnavailable("This needs a GEMINI_API_KEY in the server settings.")
    with _lock:
        if key not in _clients:
            from google import genai

            from google.genai import types

            _clients[key] = genai.Client(api_key=key, http_options=types.HttpOptions(timeout=120_000))
        return _clients[key]


def embed_model() -> str:
    return os.environ.get("EMBED_MODEL", "").strip() or "gemini-embedding-001"


def embed(settings: Any, texts: list[str], *, query: bool = False) -> list[list[float]]:
    """One vector per text (768 numbers each)."""
    from google.genai import types

    config = types.EmbedContentConfig(output_dimensionality=EMBED_DIMENSIONS,
                                      task_type="RETRIEVAL_QUERY" if query else "RETRIEVAL_DOCUMENT")
    vectors: list[list[float]] = []
    for start in range(0, len(texts), EMBED_BATCH):
        batch = texts[start:start + EMBED_BATCH]
        result = client(settings).models.embed_content(model=embed_model(), contents=batch, config=config)
        vectors.extend(list(e.values or []) for e in (result.embeddings or []))
    if len(vectors) != len(texts):
        raise AIUnavailable("The embedding service returned an unexpected answer.")
    return vectors


def image_model(settings: Any) -> str:
    """IMAGE_MODEL, or the newest Gemini "flash image" model this key can use."""
    configured = os.environ.get("IMAGE_MODEL", "").strip()
    if configured:
        return configured
    with _lock:
        if settings.gemini_api_key in _image_model:
            return _image_model[settings.gemini_api_key]
    names = []
    try:
        for m in client(settings).models.list():
            name = (m.name or "").removeprefix("models/")
            actions = m.supported_actions or []
            if "image" in name and "flash" in name and ("generateContent" in actions or not actions):
                names.append(name)
    except AIUnavailable:
        raise
    except Exception:
        log.warning("Couldn't list Gemini models; using the default picture model", exc_info=True)
    stable = [n for n in names if "preview" not in n and "exp" not in n] or names  # prefer stable models
    chosen = sorted(stable, key=_version_key)[-1] if stable else "gemini-2.5-flash-image"
    with _lock:
        _image_model[settings.gemini_api_key] = chosen
    return chosen


def _version_key(name: str) -> tuple:
    import re

    return tuple(int(x) for x in re.findall(r"\d+", name)[:3]) + (len(name),)


def generate_image(settings: Any, prompt: str, source: tuple[bytes, str] | None = None) -> tuple[bytes, str, str]:
    """(picture bytes, mime type, any text the model added)."""
    from google.genai import types

    contents: list[Any] = []
    if source:
        contents.append(types.Part.from_bytes(data=source[0], mime_type=source[1]))
    contents.append(prompt)
    response = client(settings).models.generate_content(
        model=image_model(settings), contents=contents,
        config=types.GenerateContentConfig(response_modalities=["IMAGE", "TEXT"]),
    )
    note = []
    for cand in response.candidates or []:
        for part in (cand.content.parts if cand.content else None) or []:
            if part.inline_data and part.inline_data.data:
                return part.inline_data.data, part.inline_data.mime_type or "image/png", " ".join(note)
            if part.text:
                note.append(part.text)
    reason = " ".join(note).strip()
    raise AIUnavailable(f"No picture came back{': ' + reason[:300] if reason else ' (it may have been blocked)'}.")
