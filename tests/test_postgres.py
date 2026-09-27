"""Runs Jarvis's database code against a real Postgres server (as used by Supabase).

Uses the `pgserver` package to start a throwaway Postgres; skipped if unavailable.
"""

from datetime import datetime, timedelta, timezone

import pytest

from jarvis.app import build_context
from jarvis.brain import resolve_action
from jarvis.db import PostgresDatabase
from jarvis.scheduler import fire_due_reminders
from jarvis.tools import REGISTRY, ToolError, load_all


@pytest.fixture(scope="module")
def pg_url(tmp_path_factory):
    pgserver = pytest.importorskip("pgserver")
    try:
        server = pgserver.get_server(tmp_path_factory.mktemp("pg"), cleanup_mode="stop")
    except Exception as exc:  # no permission to run postgres here, etc.
        pytest.skip(f"Postgres unavailable: {exc}")
    yield server.get_uri()
    server.cleanup()


@pytest.fixture
def pg(pg_url):
    db = PostgresDatabase(pg_url)
    for table in ("facts", "notes", "todos", "reminders", "contacts", "conversations",
                  "pending_actions", "phone_calls"):
        db.execute(f"DELETE FROM {table}")
    return db


def run(ctx, tool_name, **args):
    load_all()
    return REGISTRY[tool_name].handler(ctx, args)


def test_basic_operations(pg):
    new_id = pg.execute("INSERT INTO facts (fact, category, created_at) VALUES (?, ?, ?)", ("Likes tea", "p", "t"))
    assert isinstance(new_id, int) and new_id > 0
    assert pg.query("SELECT fact FROM facts WHERE id = ?", (new_id,)) == [{"fact": "Likes tea"}]
    assert pg.execute("UPDATE facts SET fact = ? WHERE id = ?", ("Likes coffee", new_id)) == 1
    assert pg.execute("DELETE FROM facts WHERE id = ?", (new_id + 1000,)) == 0
    pg.save_conversation("main", [{"role": "user", "content": "hi"}])
    pg.save_conversation("main", [{"role": "user", "content": "hi again"}])
    assert pg.load_conversation("main") == [{"role": "user", "content": "hi again"}]
    # A literal % in SQL next to placeholders (used when finishing phone calls).
    call = pg.execute("INSERT INTO phone_calls (direction, number, created_at) VALUES ('inbound', ?, ?)", ("+1", "t"))
    sql = "UPDATE phone_calls SET status = ? WHERE id = ? AND status NOT LIKE 'done:%'"
    assert pg.execute(sql, ("done:completed", call)) == 1
    assert pg.execute(sql, ("done:completed", call)) == 0


def test_tools_on_postgres(pg, settings):
    ctx = build_context(settings, db=pg)
    run(ctx, "remember_fact", fact="My sister is called Maya", category="People")
    assert "Maya" in run(ctx, "recall_facts", query="SISTER")  # case-insensitive search
    run(ctx, "add_note", title="Gift Ideas", body="Watch")
    assert "Gift Ideas" in run(ctx, "search_notes", query="gift")
    run(ctx, "add_todo", task="Deploy Jarvis")
    todo = pg.one("SELECT id FROM todos")["id"]
    run(ctx, "complete_todo", id=todo)
    assert "[x]" in run(ctx, "list_todos", include_done=True)
    run(ctx, "add_contact", name="Mom", phone="+971501234567")
    run(ctx, "add_contact", name="mom", phone="+971509999999")  # updates, doesn't duplicate
    assert run(ctx, "list_contacts") == "Mom: +971509999999"
    with pytest.raises(ToolError):
        run(ctx, "delete_contact", name="Nobody")
    run(ctx, "delete_contact", name="MOM")
    assert run(ctx, "list_contacts") == "No contacts saved yet."


def test_reminders_and_approvals_on_postgres(pg, settings, twilio):
    ctx = build_context(settings, db=pg)
    events = []
    ctx.notifier.subscribe(events.append)
    run(ctx, "set_reminder", message="Stretch", in_minutes=5)
    past = (datetime.now(timezone.utc) - timedelta(seconds=1)).isoformat(timespec="seconds")
    pg.execute("UPDATE reminders SET due_at = ?", (past,))
    assert fire_due_reminders(ctx) == 1 and events[0]["message"] == "Reminder: Stretch"
    assert fire_due_reminders(ctx) == 0

    action = pg.execute("INSERT INTO pending_actions (tool, input, summary, created_at) VALUES (?, ?, ?, ?)",
                        ("add_todo", '{"task": "Approved task"}', "Add a to-do", "t"))
    _, result = resolve_action(ctx, action, approve=True)
    assert "Added to-do" in result
    with pytest.raises(ToolError):
        resolve_action(ctx, action, approve=True)
