"""Pictures Jarvis makes: stored (newest 40) so the dashboard and Telegram can show them.

The most recent picture (made by Jarvis or sent by you) is also kept in memory
for a while, so "make it darker" or "turn this photo into a cartoon" can edit it.
"""

from __future__ import annotations

import base64
import threading
import time

from jarvis.db import utcnow
from jarvis.tools import Context

KEEP = 40
REMEMBER_SECONDS = 30 * 60
_last: dict[int, tuple[float, bytes, str]] = {}   # id(ctx) -> (when, picture, mime)
_lock = threading.Lock()


def save(ctx: Context, prompt: str, data: bytes, mime: str) -> int:
    image_id = ctx.db.execute("INSERT INTO images (prompt, mime, data, created_at) VALUES (?, ?, ?, ?)",
                              (prompt[:1000], mime, base64.b64encode(data).decode(), utcnow()))
    newest = ctx.db.query("SELECT id FROM images ORDER BY id DESC LIMIT 1 OFFSET ?", (KEEP - 1,))
    if newest:
        ctx.db.execute("DELETE FROM images WHERE id < ?", (newest[0]["id"],))
    remember(ctx, data, mime)
    return image_id


def get(ctx: Context, image_id: int) -> tuple[bytes, str] | None:
    row = ctx.db.one("SELECT mime, data FROM images WHERE id = ?", (image_id,))
    return (base64.b64decode(row["data"]), row["mime"]) if row else None


def latest_id(ctx: Context) -> int:
    row = ctx.db.one("SELECT MAX(id) AS n FROM images")
    return int(row["n"] or 0) if row else 0


def made_since(ctx: Context, after_id: int) -> list[int]:
    return [r["id"] for r in ctx.db.query("SELECT id FROM images WHERE id > ? ORDER BY id", (after_id,))]


def remember(ctx: Context, data: bytes, mime: str) -> None:
    with _lock:
        _last[id(ctx)] = (time.time(), data, mime)


def last(ctx: Context) -> tuple[bytes, str] | None:
    with _lock:
        found = _last.get(id(ctx))
    if found and time.time() - found[0] < REMEMBER_SECONDS:
        return found[1], found[2]
    return None
