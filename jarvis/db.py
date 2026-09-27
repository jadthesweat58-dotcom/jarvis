"""SQLite storage for everything Jarvis remembers."""

from __future__ import annotations

import json
import sqlite3
import threading
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

SCHEMA = """
CREATE TABLE IF NOT EXISTS facts (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    fact TEXT NOT NULL,
    category TEXT NOT NULL DEFAULT 'general',
    created_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS notes (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    title TEXT NOT NULL,
    body TEXT NOT NULL DEFAULT '',
    created_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS todos (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    task TEXT NOT NULL,
    due TEXT,
    done INTEGER NOT NULL DEFAULT 0,
    created_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS reminders (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    message TEXT NOT NULL,
    due_at TEXT NOT NULL,              -- UTC ISO timestamp
    notify_by TEXT NOT NULL DEFAULT '["app"]',
    status TEXT NOT NULL DEFAULT 'pending',   -- pending | fired | cancelled
    created_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS contacts (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL UNIQUE COLLATE NOCASE,
    phone TEXT NOT NULL,
    relationship TEXT NOT NULL DEFAULT '',
    created_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS conversations (
    id TEXT PRIMARY KEY,
    messages TEXT NOT NULL DEFAULT '[]',
    updated_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS pending_actions (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    tool TEXT NOT NULL,
    input TEXT NOT NULL,
    summary TEXT NOT NULL,
    status TEXT NOT NULL DEFAULT 'pending',   -- pending | approved | denied
    result TEXT,
    created_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS phone_calls (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    call_sid TEXT,
    direction TEXT NOT NULL,           -- outbound | inbound
    number TEXT NOT NULL,
    contact_name TEXT NOT NULL DEFAULT '',
    purpose TEXT NOT NULL DEFAULT '',
    with_owner INTEGER NOT NULL DEFAULT 0,
    transcript TEXT NOT NULL DEFAULT '[]',
    status TEXT NOT NULL DEFAULT 'started',
    created_at TEXT NOT NULL
);
"""


def utcnow() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


class Database:
    poll_interval = 2.0  # how often the reminder loop checks for due reminders (seconds)

    def __init__(self, path: Path | str):
        self.path = str(path)
        if self.path != ":memory:":
            Path(self.path).parent.mkdir(parents=True, exist_ok=True)
        self._lock = threading.RLock()
        self._conn = sqlite3.connect(self.path, check_same_thread=False)
        self._conn.row_factory = sqlite3.Row
        with self._lock:
            self._conn.executescript(SCHEMA)
            self._conn.commit()

    def execute(self, sql: str, params: tuple | list = ()) -> int:
        """Run a write statement. Returns the new row id for an INSERT, otherwise
        the number of rows changed."""
        with self._lock:
            cur = self._conn.execute(sql, params)
            self._conn.commit()
            if sql.lstrip().upper().startswith("INSERT"):
                return cur.lastrowid or 0
            return cur.rowcount

    def query(self, sql: str, params: tuple | list = ()) -> list[dict[str, Any]]:
        with self._lock:
            return [dict(r) for r in self._conn.execute(sql, params).fetchall()]

    def one(self, sql: str, params: tuple | list = ()) -> dict[str, Any] | None:
        rows = self.query(sql, params)
        return rows[0] if rows else None

    # --- conversations -------------------------------------------------------
    def load_conversation(self, conv_id: str) -> list[dict]:
        row = self.one("SELECT messages FROM conversations WHERE id = ?", (conv_id,))
        return json.loads(row["messages"]) if row else []

    def save_conversation(self, conv_id: str, messages: list[dict]) -> None:
        self.execute(
            "INSERT INTO conversations (id, messages, updated_at) VALUES (?, ?, ?) "
            "ON CONFLICT(id) DO UPDATE SET messages = excluded.messages, updated_at = excluded.updated_at",
            (conv_id, json.dumps(messages), utcnow()),
        )

    def delete_conversation(self, conv_id: str) -> None:
        self.execute("DELETE FROM conversations WHERE id = ?", (conv_id,))


class TursoDatabase(Database):
    """The same database, kept online in Turso (hosted SQLite) instead of a local
    file, so a free cloud host that wipes its disk doesn't make Jarvis forget.

    Talks to Turso's "SQL over HTTP" API (/v2/pipeline), so no extra packages
    are needed.
    """

    # Checking for due reminders every 2s would waste the free tier's read quota.
    poll_interval = 15.0

    def __init__(self, url: str, auth_token: str, client: Any = None):
        import httpx

        base = url.strip().rstrip("/")
        if base.startswith("libsql://"):
            base = "https://" + base[len("libsql://"):]
        self.path = base
        self._endpoint = base + "/v2/pipeline"
        self._headers = {"Authorization": f"Bearer {auth_token}"} if auth_token else {}
        self._http = client or httpx.Client(timeout=20)
        self._lock = threading.RLock()
        for statement in SCHEMA.split(";"):
            if statement.strip():
                self._run(statement)

    @staticmethod
    def _encode(value: Any) -> dict:
        if value is None:
            return {"type": "null"}
        if isinstance(value, bool):
            return {"type": "integer", "value": str(int(value))}
        if isinstance(value, int):
            return {"type": "integer", "value": str(value)}
        if isinstance(value, float):
            return {"type": "float", "value": value}
        if isinstance(value, bytes):
            import base64

            return {"type": "blob", "base64": base64.b64encode(value).decode()}
        return {"type": "text", "value": str(value)}

    @staticmethod
    def _decode(value: dict) -> Any:
        kind = value.get("type")
        if kind == "integer":
            return int(value["value"])
        if kind == "float":
            return float(value["value"])
        if kind == "blob":
            import base64

            return base64.b64decode(value["base64"])
        return value.get("value")  # text, or None for null

    def _run(self, sql: str, params: tuple | list = ()) -> dict:
        body = {"requests": [
            {"type": "execute", "stmt": {"sql": sql, "args": [self._encode(p) for p in params]}},
            {"type": "close"},
        ]}
        with self._lock:
            resp = self._http.post(self._endpoint, json=body, headers=self._headers)
        if resp.status_code == 401:
            raise RuntimeError("Turso rejected the token. Check TURSO_AUTH_TOKEN.")
        resp.raise_for_status()
        result = resp.json()["results"][0]
        if result.get("type") == "error":
            raise RuntimeError(f"Turso error: {result['error'].get('message')}")
        return result["response"]["result"]

    def execute(self, sql: str, params: tuple | list = ()) -> int:
        result = self._run(sql, params)
        if sql.lstrip().upper().startswith("INSERT"):
            return int(result.get("last_insert_rowid") or 0)
        return int(result.get("affected_row_count") or 0)

    def query(self, sql: str, params: tuple | list = ()) -> list[dict[str, Any]]:
        result = self._run(sql, params)
        names = [c.get("name") for c in result.get("cols", [])]
        return [dict(zip(names, (self._decode(v) for v in row))) for row in result.get("rows", [])]


class PostgresDatabase(Database):
    """The same database kept in Postgres, e.g. a free Supabase project, so a free
    cloud host that wipes its disk doesn't make Jarvis forget.

    Jarvis's queries are written in SQL that works on both SQLite and Postgres;
    this class only translates the "?" placeholders and returns new row ids.
    """

    poll_interval = 5.0

    def __init__(self, url: str):
        self.path = url
        self._lock = threading.RLock()
        self._conn = None
        schema = SCHEMA.replace("INTEGER PRIMARY KEY AUTOINCREMENT", "BIGSERIAL PRIMARY KEY")
        schema = schema.replace(" COLLATE NOCASE", "")
        for statement in schema.split(";"):
            if statement.strip():
                self._run(statement, (), fetch=False)

    def _connect(self):
        import psycopg
        from psycopg.rows import dict_row

        # prepare_threshold=None: Supabase's connection pooler can't keep prepared statements.
        return psycopg.connect(self.path, autocommit=True, prepare_threshold=None,
                               row_factory=dict_row, connect_timeout=15)

    @staticmethod
    def _translate(sql: str) -> str:
        return sql.replace("%", "%%").replace("?", "%s")

    def _run(self, sql: str, params: tuple | list, fetch: bool):
        import psycopg

        with self._lock:
            for attempt in (1, 2):
                try:
                    if self._conn is None or self._conn.closed:
                        self._conn = self._connect()
                    with self._conn.cursor() as cur:
                        cur.execute(self._translate(sql), tuple(params))
                        rows = cur.fetchall() if fetch and cur.description else []
                        return rows, cur.rowcount
                except psycopg.OperationalError:
                    # The pooler drops idle connections; reconnect once and retry.
                    self._conn = None
                    if attempt == 2:
                        raise

    def execute(self, sql: str, params: tuple | list = ()) -> int:
        if sql.lstrip().upper().startswith("INSERT"):
            rows, _ = self._run(sql.rstrip() + " RETURNING id", params, fetch=True)
            new_id = rows[0]["id"] if rows else 0
            return new_id if isinstance(new_id, int) else 0
        _, count = self._run(sql, params, fetch=False)
        return max(count, 0)

    def query(self, sql: str, params: tuple | list = ()) -> list[dict[str, Any]]:
        rows, _ = self._run(sql, params, fetch=True)
        return [dict(r) for r in rows]


def open_database(settings: Any) -> Database:
    """Postgres (e.g. Supabase) when DATABASE_URL is set, Turso when TURSO_DATABASE_URL
    is set, otherwise a local SQLite file."""
    if settings.database_url:
        return PostgresDatabase(settings.database_url)
    if settings.turso_database_url:
        return TursoDatabase(settings.turso_database_url, settings.turso_auth_token)
    return Database(settings.db_path)
