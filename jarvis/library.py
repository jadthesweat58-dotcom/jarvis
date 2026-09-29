"""Jarvis's second brain: a searchable library of your documents.

Files you attach (and web pages you ask Jarvis to save) are split into
passages and indexed with Gemini embeddings, so later you can ask "what did the
lease say about the notice period?" and Jarvis finds the right passage. Without
a Gemini key (or if embedding fails) it falls back to keyword search.
"""

from __future__ import annotations

import json
import logging
import re
from typing import Any

import numpy as np

from jarvis.db import utcnow
from jarvis.tools import Context

log = logging.getLogger("jarvis.library")

CHUNK_CHARS = 1500
OVERLAP = 200
MAX_DOCUMENT_CHARS = 200_000
MAX_CHUNKS = 6000          # ~9 million characters in all; keeps memory small on a free server
INSERT_BATCH = 40
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


class LibraryFull(ValueError):
    pass


def add_document(ctx: Context, name: str, text: str, source: str = "file") -> int:
    """Save a document to the library. Returns its id."""
    text = text[:MAX_DOCUMENT_CHARS]
    pieces = chunk(text)
    stored = int(ctx.db.one("SELECT COUNT(*) AS n FROM chunks")["n"] or 0)
    if stored + len(pieces) > MAX_CHUNKS:
        raise LibraryFull("The library is full. Remove some documents (Library in the sidebar) to add more.")
    summary = re.sub(r"\s+", " ", text[:280]).strip()
    doc_id = ctx.db.execute(
        "INSERT INTO documents (name, source, chars, summary, created_at) VALUES (?, ?, ?, ?, ?)",
        (name[:200], source[:500], len(text), summary, utcnow()))
    vectors = _embed(ctx, pieces) or [None] * len(pieces)
    rows = [(doc_id, idx, piece, json.dumps([round(v, 5) for v in vec]) if vec else None)
            for idx, (piece, vec) in enumerate(zip(pieces, vectors))]
    # A few rows per statement: far fewer round trips to an online database.
    for start in range(0, len(rows), INSERT_BATCH):
        batch = rows[start:start + INSERT_BATCH]
        ctx.db.execute("INSERT INTO chunks (doc_id, idx, text, embedding) VALUES "
                       + ", ".join("(?, ?, ?, ?)" for _ in batch), [v for row in batch for v in row])
    return doc_id


def forget(ctx: Context, doc_id: int) -> bool:
    gone = [r["id"] for r in ctx.db.query("SELECT id FROM chunks WHERE doc_id = ?", (doc_id,))]
    ctx.db.execute("DELETE FROM chunks WHERE doc_id = ?", (doc_id,))
    for chunk_id in gone:
        _vector_cache.pop((id(ctx.db), chunk_id), None)
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


_vector_cache: dict[tuple[int, int], Any] = {}   # (id(db), chunk id) -> float32 vector (~3 KB)


def _vectors(ctx: Context) -> dict[int, Any]:
    """Every embedded passage's vector. Kept in memory, so each search only
    downloads vectors it hasn't seen before (the database may be online)."""
    ids = [r["id"] for r in ctx.db.query("SELECT id FROM chunks WHERE embedding IS NOT NULL")]
    key = id(ctx.db)
    missing = [i for i in ids if (key, i) not in _vector_cache]
    for start in range(0, len(missing), 200):
        batch = missing[start:start + 200]
        marks = ",".join("?" for _ in batch)
        for row in ctx.db.query(f"SELECT id, embedding FROM chunks WHERE id IN ({marks})", tuple(batch)):
            _vector_cache[(key, row["id"])] = np.asarray(json.loads(row["embedding"]), dtype=np.float32)
    return {i: _vector_cache[(key, i)] for i in ids if (key, i) in _vector_cache}


def _similarities(query: list[float], vectors: dict[int, Any]) -> list[tuple[float, int]]:
    """Cosine similarity of the question to every passage, best first."""
    if not vectors:
        return []
    ids = list(vectors)
    matrix = np.stack([vectors[i] for i in ids])
    q = np.asarray(query, dtype=np.float32)
    norms = np.linalg.norm(matrix, axis=1) * (np.linalg.norm(q) or 1.0)
    scores = matrix @ q / np.where(norms == 0, 1.0, norms)
    order = np.argsort(-scores)
    return [(float(scores[i]), ids[i]) for i in order]


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
        scored = _similarities(qvec, _vectors(ctx))
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
