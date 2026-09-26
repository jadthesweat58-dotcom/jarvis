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
