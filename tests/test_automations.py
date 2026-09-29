import json
from datetime import datetime, timedelta, timezone

import pytest
from fastapi.testclient import TestClient

from jarvis import automations
from jarvis.brain import Brain
from jarvis.server import create_app
from jarvis.tools import REGISTRY, ToolError, load_all
from tests.conftest import FakeClaude, response, text, tool_use

UTC = timezone.utc


def run(ctx, tool_name, **args):
    load_all()
    return REGISTRY[tool_name].handler(ctx, args)


def brains(ctx, *replies):
    """make_brain for the runners: every brain answers from one shared script."""
    claude = FakeClaude(*replies)
    made = []

    def make(**kw):
        made.append(kw)
        return Brain(ctx, client=claude, **kw)

    return make, claude, made


# ------------------------------------------------------------------ routines
def test_create_and_list_routine(ctx):
    ctx.settings.timezone = "Asia/Dubai"
    out = run(ctx, "create_routine", title="Weekend plans", prompt="Find fun events in Dubai this weekend",
              at="2030-10-04T18:00", repeat="weekly")
    assert "Routine #1" in out and "every week" in out
    row = ctx.db.one("SELECT * FROM routines")
    assert row["rule"] == "weekly@18:00" and row["next_run"] == "2030-10-04T14:00:00+00:00"
    assert "Weekend plans (every week; next Fri 04 Oct 2030 18:00)" in run(ctx, "list_routines")


def test_routines_never_get_private_or_risky_tools(phone_ctx):
    """Even with the phone and pictures set up, a routine only gets public-information tools."""
    phone_ctx.settings.gemini_api_key = "k"
    names = {t.name for t in automations.safe_tools(phone_ctx.settings)}
    risky = {"set_reminder", "call_me", "text_me", "remember_fact", "forget_fact", "add_contact", "list_contacts",
             "search_library", "search_notes", "get_calendar", "save_webpage", "complete_todo", "generate_image",
             "create_routine", "watch_page", "recall_facts", "add_note", "add_todo"}
    assert names and not names & risky


def test_new_routines_and_watchers_need_approval(ctx, public):
    claude = FakeClaude(
        response(tool_use("create_routine", {"title": "News", "prompt": "news", "in_minutes": 5})),
        response(text("Approve it and I'll set it up.")),
    )
    reply = Brain(ctx, client=claude).chat("every day give me news")
    assert reply.actions and "New routine \"News\"" in reply.actions[0]["summary"]
    assert ctx.db.query("SELECT id FROM routines") == []


def test_routine_runs_once_with_safe_tools_and_reports(ctx):
    events = []
    ctx.notifier.subscribe(events.append)
    run(ctx, "create_routine", title="Tech news", prompt="Top 3 tech headlines", in_minutes=1, repeat="daily")
    make, claude, made = brains(ctx, response(text("1. A. 2. B. 3. C.")))
    later = datetime.now(UTC) + timedelta(minutes=2)
    assert automations.run_due_routines(ctx, make, now=later) == 1
    assert automations.run_due_routines(ctx, make, now=later) == 0  # claimed: never twice
    tools = {t.name for t in made[0]["tools"]}
    assert tools == {"get_weather", "calculate", "convert_currency", "world_time", "prayer_times",
                     "market_quote", "read_webpage"}
    assert made[0]["remember_facts"] is False
    assert "Top 3 tech headlines" in claude.requests[0]["messages"][-1]["content"][-1]["text"]
    row = ctx.db.one("SELECT * FROM routines")
    assert row["last_result"] == "1. A. 2. B. 3. C." and datetime.fromisoformat(row["next_run"]) > later
    assert events[-1]["kind"] == "routine" and events[-1]["message"] == "Tech news: 1. A. 2. B. 3. C."
    assert not ctx.db.query("SELECT id FROM conversations WHERE id LIKE 'routine-%'")  # temp chats removed


def test_routine_failure_is_reported_not_raised(ctx):
    events = []
    ctx.notifier.subscribe(events.append)
    run(ctx, "create_routine", title="Broken", prompt="x", in_minutes=1)

    class Boom:
        beta = type("B", (), {"messages": type("M", (), {"create": staticmethod(lambda **kw: 1 / 0)})})

    automations.run_due_routines(ctx, lambda **kw: Brain(ctx, client=Boom(), **kw),
                                 now=datetime.now(UTC) + timedelta(minutes=2))
    assert "couldn't finish" in events[-1]["message"]


def test_routine_limits_and_run_now(ctx):
    for i in range(automations.MAX_ROUTINES):
        run(ctx, "create_routine", title=f"R{i}", prompt="x", in_minutes=60)
    with pytest.raises(ToolError, match="already"):
        run(ctx, "create_routine", title="one too many", prompt="x", in_minutes=60)
    before = ctx.db.one("SELECT next_run FROM routines WHERE id = 3")["next_run"]
    ctx.db.execute("UPDATE routines SET enabled = 0 WHERE id = 3")
    run(ctx, "run_routine_now", id=3)
    make, _, _ = brains(ctx, response(text("done")))
    assert automations.run_due_routines(ctx, make) == 1
    assert automations.run_due_routines(ctx, make) == 0
    row = ctx.db.one("SELECT next_run, enabled, last_result FROM routines WHERE id = 3")
    # Ran once; the regular schedule is untouched and it stays paused.
    assert row == {"next_run": before, "enabled": 0, "last_result": "done"}
    with pytest.raises(ToolError):
        run(ctx, "delete_routine", id=999)


# ------------------------------------------------------------------ watchers
def page(text_):
    return lambda url: (url, "Shop", text_)


@pytest.fixture
def public(monkeypatch):
    import socket

    from jarvis import safeurl

    def resolve(host, port, *a, **kw):
        ip = "10.0.0.1" if host == "intranet.local" else "93.184.216.34"
        return [(socket.AF_INET, socket.SOCK_STREAM, 6, "", (ip, port))]

    monkeypatch.setattr(safeurl.socket, "getaddrinfo", resolve)


def due_now(ctx):
    ctx.db.execute("UPDATE watchers SET next_check = ?", ((datetime.now(UTC) - timedelta(seconds=1)).isoformat(timespec="seconds"),))


def test_watch_condition_alerts_once(ctx, public):
    events = []
    ctx.notifier.subscribe(events.append)
    out = run(ctx, "watch_page", url="shop.example/headphones", condition="price below 500 AED", every_hours=3)
    assert "Watcher #1" in out and "every 3h" in out
    make, claude, _ = brains(ctx, response(text('{"met": false, "detail": "Now 649 AED"}')),
                             response(text('Sure: {"met": true, "detail": "Now 479 AED"}')))
    assert automations.run_due_watchers(ctx, make, fetch=page("Headphones 649 AED")) == 1
    assert events == [] and ctx.db.one("SELECT last_note FROM watchers")["last_note"] == "Now 649 AED"
    assert "price below 500 AED" in claude.requests[0]["messages"][-1]["content"][-1]["text"]
    due_now(ctx)
    automations.run_due_watchers(ctx, make, fetch=page("Headphones 479 AED"))
    assert events[-1]["kind"] == "watch" and "Now 479 AED" in events[-1]["message"]
    assert ctx.db.one("SELECT status FROM watchers")["status"] == "done"
    due_now(ctx)
    assert automations.run_due_watchers(ctx, make, fetch=page("x")) == 0  # finished watchers stay quiet


def test_watch_changes(ctx, public):
    events = []
    ctx.notifier.subscribe(events.append)
    run(ctx, "watch_page", url="https://news.example/jobs")
    make, claude, _ = brains(ctx, response(text('{"meaningful": false, "summary": "Only the date changed."}')),
                             response(text('{"meaningful": true, "summary": "A new job was posted: Designer."}')))
    automations.run_due_watchers(ctx, make, fetch=page("Jobs\nEngineer\nUpdated Monday"))
    assert claude.requests == [] and "First look" in ctx.db.one("SELECT last_note FROM watchers")["last_note"]
    due_now(ctx)
    automations.run_due_watchers(ctx, make, fetch=page("Jobs\nEngineer\nUpdated Monday"))  # same: no AI call
    assert claude.requests == []
    due_now(ctx)
    automations.run_due_watchers(ctx, make, fetch=page("Jobs\nEngineer\nUpdated Tuesday"))
    assert events == [] and "-Updated Monday" in claude.requests[0]["messages"][-1]["content"][-1]["text"]
    due_now(ctx)
    automations.run_due_watchers(ctx, make, fetch=page("Jobs\nEngineer\nDesigner\nUpdated Tuesday"))
    assert "A new job was posted: Designer." in events[-1]["message"]


def test_failing_pages_pause_after_three_tries(ctx, public):
    events = []
    ctx.notifier.subscribe(events.append)
    run(ctx, "watch_page", url="https://blocked.example/")

    def blocked(url):
        raise ToolError("The website answered with error 403.")

    for _ in range(3):
        due_now(ctx)
        automations.run_due_watchers(ctx, lambda **kw: None, fetch=blocked)
    row = ctx.db.one("SELECT status, fails FROM watchers")
    assert row == {"status": "paused", "fails": 3}
    assert len(events) == 1 and "stopped watching" in events[0]["message"] and "403" in events[0]["message"]


def test_watchers_refuse_private_addresses(ctx, public):
    with pytest.raises(ToolError, match="private network"):
        run(ctx, "watch_page", url="http://intranet.local/admin")


# ------------------------------------------------------------------ dashboard endpoints
def test_automation_endpoints(ctx, public):
    run(ctx, "create_routine", title="News", prompt="news", in_minutes=30, repeat="weekdays")
    run(ctx, "watch_page", url="https://shop.example/", condition="in stock")
    app = create_app(ctx, brain_factory=lambda **kw: Brain(ctx, client=FakeClaude(), **kw))
    client = TestClient(app, base_url="http://localhost", client=("127.0.0.1", 5000))
    data = client.get("/api/automations").json()
    assert data["routines"][0]["schedule"].startswith("every weekday at ") and data["watchers"][0]["condition"] == "in stock"
    assert "snapshot" not in data["watchers"][0]
    assert client.post("/api/automations/routine/1", json={"action": "pause"}).json() == {"ok": True}
    assert ctx.db.one("SELECT enabled FROM routines")["enabled"] == 0
    client.post("/api/automations/routine/1", json={"action": "run"})
    assert ctx.db.one("SELECT enabled, run_now FROM routines") == {"enabled": 0, "run_now": 1}
    client.post("/api/automations/watcher/1", json={"action": "pause"})
    assert ctx.db.one("SELECT status FROM watchers")["status"] == "paused"
    assert client.post("/api/automations/watcher/1", json={"action": "run"}).status_code == 409
    assert client.post("/api/automations/watcher/1", json={"action": "delete"}).json() == {"ok": True}
    assert client.post("/api/automations/watcher/1", json={"action": "delete"}).status_code == 404
    assert client.post("/api/automations/nope/1", json={"action": "run"}).status_code == 404
    assert client.post("/api/automations/routine/1", json={"action": "explode"}).status_code == 400
    assert client.get("/api/dashboard").json()["counts"]["automations"] == 0  # paused + deleted


def test_watcher_saves_ai_calls_and_keeps_changes_when_judging_fails(ctx, public):
    events = []
    ctx.notifier.subscribe(events.append)
    run(ctx, "watch_page", url="https://shop.example/", condition="price below 500 AED")
    make, claude, _ = brains(ctx, response(text('{"met": false, "detail": "Now 649 AED, see https://evil.example/x"}')))
    automations.run_due_watchers(ctx, make, fetch=page("649 AED"))
    assert ctx.db.one("SELECT last_note FROM watchers")["last_note"] == "Now 649 AED, see [link]"
    due_now(ctx)
    automations.run_due_watchers(ctx, make, fetch=page("649 AED"))  # unchanged page: no AI call
    assert len(claude.requests) == 1

    run(ctx, "watch_page", url="https://news.example/")
    ctx.db.execute("UPDATE watchers SET snapshot = 'old text' WHERE id = 2")
    ctx.db.execute("UPDATE watchers SET status = 'paused' WHERE id = 1")
    broken, _, _ = brains(ctx, response(text("not json at all")))
    due_now(ctx)
    ctx.db.execute("UPDATE watchers SET status = 'active' WHERE id = 2")
    automations.run_due_watchers(ctx, broken, fetch=page("new text"))
    row = ctx.db.one("SELECT snapshot, last_note FROM watchers WHERE id = 2")
    assert row["snapshot"] == "old text" and "couldn't judge" in row["last_note"]  # looked at again next time
    assert events == []


def test_pause_during_a_check_is_kept(ctx, public):
    run(ctx, "watch_page", url="https://shop.example/", condition="in stock")
    w = ctx.db.one("SELECT * FROM watchers")
    ctx.db.execute("UPDATE watchers SET status = 'paused'")  # the user pauses while the check runs
    make, _, _ = brains(ctx, response(text('{"met": true, "detail": "In stock now"}')))
    automations.check_watcher(ctx, make, w, fetch=page("In stock"))
    assert ctx.db.one("SELECT status FROM watchers")["status"] == "paused"
