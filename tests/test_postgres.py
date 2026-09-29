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
                  "pending_actions", "phone_calls", "kv", "usage_log", "push_subscriptions",
                  "routines", "watchers", "documents", "chunks", "images"):
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


def test_key_value_state_on_postgres(pg):
    assert pg.get_kv("last_briefing") == ""
    pg.set_kv("last_briefing", "2026-09-27")
    pg.set_kv("last_briefing", "2026-09-28")
    assert pg.get_kv("last_briefing") == "2026-09-28"


def test_new_tables_on_postgres(pg, settings, monkeypatch):
    from jarvis import push, safeurl, usage

    ctx = build_context(settings, db=pg)
    usage.record(ctx, {"ai_calls": 1, "ai_tokens_in": 500})
    usage.record(ctx, {"ai_calls": 1, "ai_tokens_in": 250})
    assert usage.summary(ctx)["today"]["ai_tokens_in"] == 750  # upsert adds up

    monkeypatch.setattr(safeurl.socket, "getaddrinfo",
                        lambda host, port, *a, **kw: [(2, 1, 6, "", ("142.250.1.1", port))])
    sub = {"endpoint": "https://fcm.googleapis.com/fcm/send/x", "keys": {"p256dh": "k", "auth": "a"}}
    push.save_subscription(ctx, sub)
    push.save_subscription(ctx, sub)
    assert push.count(ctx) == 1
    assert push.public_key(ctx) == push.public_key(ctx)

    # A repeating reminder moves on instead of being marked fired.
    run(ctx, "set_reminder", message="Water plants", in_minutes=5, repeat="daily")
    past = (datetime.now(timezone.utc) - timedelta(seconds=1)).isoformat(timespec="seconds")
    pg.execute("UPDATE reminders SET due_at = ?", (past,))
    assert fire_due_reminders(ctx) == 1 and fire_due_reminders(ctx) == 0
    row = pg.one("SELECT status, due_at FROM reminders")
    assert row["status"] == "pending" and row["due_at"] > past


def test_automations_library_and_pictures_on_postgres(pg, settings, monkeypatch):
    from jarvis import automations, images, library

    ctx = build_context(settings, db=pg)
    run(ctx, "create_routine", title="News", prompt="news", in_minutes=1)
    later = datetime.now(timezone.utc) + timedelta(minutes=5)
    ran = []
    monkeypatch.setattr(automations, "run_routine", lambda c, mb, r: ran.append(r["id"]))
    assert automations.run_due_routines(ctx, None, now=later) == 1 and automations.run_due_routines(ctx, None, now=later) == 0

    monkeypatch.setattr("jarvis.safeurl.socket.getaddrinfo",
                        lambda host, port, *a, **kw: [(2, 1, 6, "", ("93.184.216.34", port))])
    run(ctx, "watch_page", url="https://shop.example/")
    automations.run_due_watchers(ctx, None, fetch=lambda url: (url, "Shop", "Hello"))
    assert pg.one("SELECT snapshot FROM watchers")["snapshot"] == "Hello"

    doc = library.add_document(ctx, "Notes.txt", "The wifi password for the office is on the fridge.")
    assert library.search(ctx, "wifi password")[0]["doc_id"] == doc  # keyword search (no key in tests)
    assert library.forget(ctx, doc)

    first = images.save(ctx, "p", b"PNG", "image/png")
    assert images.get(ctx, first) == (b"PNG", "image/png") and images.made_since(ctx, 0) == [first]
