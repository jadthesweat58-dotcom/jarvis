import base64
import json
import sqlite3

import httpx
import pytest

from jarvis.app import build_context
from jarvis.db import Database, TursoDatabase, open_database
from jarvis.tools import REGISTRY, load_all


class FakeTurso:
    """Answers Turso's /v2/pipeline API from a real in-memory SQLite database."""

    def __init__(self, token="secret"):
        self.db = sqlite3.connect(":memory:")
        self.token = token
        self.requests = 0

    @staticmethod
    def _decode(v):
        return {"null": lambda: None, "integer": lambda: int(v["value"]), "float": lambda: v["value"],
                "text": lambda: v["value"], "blob": lambda: base64.b64decode(v["base64"])}[v["type"]]()

    @staticmethod
    def _encode(v):
        if v is None:
            return {"type": "null"}
        if isinstance(v, int):
            return {"type": "integer", "value": str(v)}
        if isinstance(v, float):
            return {"type": "float", "value": v}
        return {"type": "text", "value": v}

    def handle(self, request: httpx.Request) -> httpx.Response:
        assert request.url.path == "/v2/pipeline"
        if request.headers.get("authorization") != f"Bearer {self.token}":
            return httpx.Response(401)
        self.requests += 1
        results = []
        for req in json.loads(request.content)["requests"]:
            if req["type"] == "close":
                results.append({"type": "ok", "response": {"type": "close"}})
                continue
            stmt = req["stmt"]
            try:
                cur = self.db.execute(stmt["sql"], [self._decode(a) for a in stmt.get("args", [])])
                rows = cur.fetchall()
                self.db.commit()
            except sqlite3.Error as exc:
                results.append({"type": "error", "error": {"message": str(exc), "code": "SQLITE_ERROR"}})
                continue
            results.append({"type": "ok", "response": {"type": "execute", "result": {
                "cols": [{"name": d[0], "decltype": None} for d in (cur.description or [])],
                "rows": [[self._encode(v) for v in row] for row in rows],
                "affected_row_count": max(cur.rowcount, 0),
                "last_insert_rowid": str(cur.lastrowid) if cur.lastrowid else None,
            }}})
        return httpx.Response(200, json={"baton": None, "base_url": None, "results": results})


@pytest.fixture
def turso():
    server = FakeTurso()
    client = httpx.Client(transport=httpx.MockTransport(server.handle))
    return server, TursoDatabase("libsql://jarvis-me.turso.io", "secret", client=client)


def test_turso_database_behaves_like_sqlite(turso):
    server, db = turso
    assert db.path == "https://jarvis-me.turso.io" and db.poll_interval > 2
    fid = db.execute("INSERT INTO facts (fact, category, created_at) VALUES (?, ?, ?)", ("Likes tea", "prefs", "t"))
    assert fid == 1
    assert db.query("SELECT id, fact FROM facts") == [{"id": 1, "fact": "Likes tea"}]
    assert db.execute("UPDATE facts SET fact = ? WHERE id = ?", ("Likes coffee", 1)) == 1
    assert db.execute("DELETE FROM facts WHERE id = ?", (99,)) == 0
    db.save_conversation("main", [{"role": "user", "content": "hi"}])
    db.save_conversation("main", [{"role": "user", "content": "hi again"}])
    assert db.load_conversation("main") == [{"role": "user", "content": "hi again"}]
    with pytest.raises(RuntimeError, match="Turso error"):
        db.query("SELECT * FROM nope")


def test_jarvis_tools_work_on_turso(turso, settings):
    _, db = turso
    ctx = build_context(settings, db=db)
    load_all()
    REGISTRY["add_todo"].handler(ctx, {"task": "Deploy Jarvis"})
    REGISTRY["complete_todo"].handler(ctx, {"id": 1})
    assert "[x] #1 Deploy Jarvis" in REGISTRY["list_todos"].handler(ctx, {"include_done": True})
    REGISTRY["add_contact"].handler(ctx, {"name": "Mom", "phone": "+971501234567"})
    REGISTRY["add_contact"].handler(ctx, {"name": "mom", "phone": "+971509999999"})  # upsert
    assert "Mom: +971509999999" in REGISTRY["list_contacts"].handler(ctx, {})


def test_bad_token_is_explained():
    server = FakeTurso(token="right")
    client = httpx.Client(transport=httpx.MockTransport(server.handle))
    with pytest.raises(RuntimeError, match="TURSO_AUTH_TOKEN"):
        TursoDatabase("libsql://x.turso.io", "wrong", client=client)


def test_open_database_picks_backend(settings):
    assert type(open_database(settings)) is Database
