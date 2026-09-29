"""Jarvis's second brain: a searchable library of your documents.

Files you attach (and web pages you ask Jarvis to save) are split into
passages and indexed with Gemini embeddings, so later you can ask "what did the
lease say about the notice period?" and Jarvis finds the right passage. Without
a Gemini key (or if embedding fails) it falls back to keyword search.
"""

from __future__ import annotations

import json
import logging
import math
import re
from typing import Any

from jarvis.db import utcnow
from jarvis.tools import Context

log = logging.getLogger("jarvis.library")

CHUNK_CHARS = 1500
OVERLAP = 200
MAX_DOCUMENT_CHARS = 200_000
BACKFILL_BATCH = 100


def chunk(text: str) -> list[str]:
    """Split text into overlapping passages, preferring paragraph and sentence breaks."""
    text = re.sub(r"\n{3,}", "\n\n", text).strip()
    pieces: list[str] = []
    start = 0
    while start < len(text):
        end = min(start + CHUNK_CHARS, len(text))
        if end < len(text):
            window = text[start:end]
            cut = max(window.rfind("\n\n"), window.rfind(". "), window.rfind("\n"))
            if cut > CHUNK_CHARS // 2:
                end = start + cut + 1
        piece = text[start:end].strip()
        if piece:
            pieces.append(piece)
        if end >= len(text):
            break
        start = max(end - OVERLAP, start + 1)
    return pieces


def _embed(ctx: Context, texts: list[str], query: bool = False) -> list[list[float]] | None:
    if not ctx.settings.gemini_api_key or not texts:
        return None
    from jarvis import google_ai

    try:
        return google_ai.embed(ctx.settings, texts, query=query)
    except Exception as exc:
        log.warning("Embedding failed (%s); keyword search still works", type(exc).__name__)
        return None


def add_document(ctx: Context, name: str, text: str, source: str = "file") -> int:
    """Save a document to the library. Returns its id."""
    text = text[:MAX_DOCUMENT_CHARS]
    pieces = chunk(text)
    summary = re.sub(r"\s+", " ", text[:280]).strip()
    doc_id = ctx.db.execute(
        "INSERT INTO documents (name, source, chars, summary, created_at) VALUES (?, ?, ?, ?, ?)",
        (name[:200], source[:500], len(text), summary, utcnow()))
    vectors = _embed(ctx, pieces) or [None] * len(pieces)
    for idx, (piece, vec) in enumerate(zip(pieces, vectors)):
        ctx.db.execute("INSERT INTO chunks (doc_id, idx, text, embedding) VALUES (?, ?, ?, ?)",
                       (doc_id, idx, piece, json.dumps([round(v, 5) for v in vec]) if vec else None))
    return doc_id


def forget(ctx: Context, doc_id: int) -> bool:
    ctx.db.execute("DELETE FROM chunks WHERE doc_id = ?", (doc_id,))
    return bool(ctx.db.execute("DELETE FROM documents WHERE id = ?", (doc_id,)))


def documents(ctx: Context) -> list[dict[str, Any]]:
    return ctx.db.query("SELECT id, name, source, chars, summary, created_at FROM documents ORDER BY id DESC")


def _backfill(ctx: Context) -> None:
    """Embed passages saved while embedding wasn't available."""
    rows = ctx.db.query("SELECT id, text FROM chunks WHERE embedding IS NULL ORDER BY id LIMIT ?", (BACKFILL_BATCH,))
    vectors = _embed(ctx, [r["text"] for r in rows]) if rows else None
    for row, vec in zip(rows, vectors or []):
        ctx.db.execute("UPDATE chunks SET embedding = ? WHERE id = ?",
                       (json.dumps([round(v, 5) for v in vec]), row["id"]))


_vector_cache: dict[tuple[int, int], list[float]] = {}   # (id(db), chunk id) -> vector


def _vectors(ctx: Context) -> dict[int, list[float]]:
    """Every embedded passage's vector. Kept in memory, so each search only
    downloads vectors it hasn't seen before (the database may be online)."""
    ids = [r["id"] for r in ctx.db.query("SELECT id FROM chunks WHERE embedding IS NOT NULL")]
    key = id(ctx.db)
    missing = [i for i in ids if (key, i) not in _vector_cache]
    for start in range(0, len(missing), 200):
        batch = missing[start:start + 200]
        marks = ",".join("?" for _ in batch)
        for row in ctx.db.query(f"SELECT id, embedding FROM chunks WHERE id IN ({marks})", tuple(batch)):
            _vector_cache[(key, row["id"])] = json.loads(row["embedding"])
    return {i: _vector_cache[(key, i)] for i in ids if (key, i) in _vector_cache}


def _cosine(a: list[float], b: list[float]) -> float:
    dot = sum(x * y for x, y in zip(a, b))
    na = math.sqrt(sum(x * x for x in a))
    nb = math.sqrt(sum(y * y for y in b))
    return dot / (na * nb) if na and nb else 0.0


def search(ctx: Context, query: str, k: int = 6) -> list[dict[str, Any]]:
    """The passages that best match the question, best first."""
    query = query.strip()
    if not query:
        return []
    names = {d["id"]: d["name"] for d in ctx.db.query("SELECT id, name FROM documents")}
    if not names:
        return []
    qvec = None
    if ctx.settings.gemini_api_key:
        _backfill(ctx)
        found = _embed(ctx, [query], query=True)
        qvec = found[0] if found else None
    if qvec:
        vectors = _vectors(ctx)
        scored = sorted(((_cosine(qvec, v), cid) for cid, v in vectors.items()), reverse=True)
        top = [(score, cid) for score, cid in scored[:k] if score > 0.3]
        if top:
            marks = ",".join("?" for _ in top)
            rows = {r["id"]: r for r in ctx.db.query(
                f"SELECT id, doc_id, idx, text FROM chunks WHERE id IN ({marks})", tuple(c for _, c in top))}
            return [{**rows[c], "score": round(score, 3), "name": names.get(rows[c]["doc_id"], "?")}
                    for score, c in top if c in rows]
    # Keyword fallback: passages containing the most of the question's words.
    words = [w for w in re.findall(r"\w{3,}", query.lower())][:8]
    if not words:
        return []
    where = " OR ".join("lower(text) LIKE ?" for _ in words)
    rows = ctx.db.query(f"SELECT id, doc_id, idx, text FROM chunks WHERE {where} LIMIT 200",
                        tuple(f"%{w}%" for w in words))
    ranked = sorted(rows, key=lambda r: sum(r["text"].lower().count(w) for w in words), reverse=True)
    return [{**r, "name": names.get(r["doc_id"], "?")} for r in ranked[:k]]
