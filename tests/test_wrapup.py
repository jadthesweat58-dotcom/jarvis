from datetime import datetime, timedelta, timezone
from zoneinfo import ZoneInfo

from jarvis import wrapup
from jarvis.brain import Brain
from jarvis.tools import REGISTRY, load_all
from tests.conftest import FakeClaude, response, text

DUBAI = ZoneInfo("Asia/Dubai")
UTC = timezone.utc


def setup_day(ctx):
    ctx.settings.timezone = "Asia/Dubai"
    ctx.settings.my_name = "Jad"
    old = (datetime.now(UTC) - timedelta(days=5)).isoformat(timespec="seconds")
    now = datetime.now(UTC).isoformat(timespec="seconds")
    ctx.db.execute("INSERT INTO todos (task, priority, created_at) VALUES ('Renew car registration', 'high', ?)", (old,))
    ctx.db.execute("INSERT INTO todos (task, priority, created_at) VALUES ('Buy milk', 'low', ?)", (now,))
    ctx.db.execute("INSERT INTO todos (task, priority, done, done_at, created_at) VALUES ('Deploy Jarvis', 'high', 1, ?, ?)",
                   (now, old))
    ctx.db.execute("INSERT INTO todos (task, priority, done, done_at, created_at) VALUES ('Old win', 'med', 1, ?, ?)",
                   (old, old))
    tomorrow_9 = (datetime.now(DUBAI) + timedelta(days=1)).replace(hour=9, minute=0, second=0, microsecond=0)
    ctx.db.execute("INSERT INTO reminders (message, due_at, created_at) VALUES ('Dentist', ?, 'x')",
                   (tomorrow_9.astimezone(UTC).isoformat(timespec="seconds"),))
    return ctx


def test_gather_and_fallback(ctx):
    facts = wrapup.gather(setup_day(ctx))
    assert facts["done_today"] == ["Deploy Jarvis"]
    assert facts["stale"] == ["Renew car registration"] and facts["open_count"] == 2
    assert facts["tomorrow_reminders"] == [{"time": "09:00", "message": "Dentist"}]
    text_ = wrapup.as_text(facts)
    assert "Finished today: Deploy Jarvis" in text_ and "waiting 3+ days: Renew car registration" in text_
    plain = wrapup.fallback(facts)
    assert plain.startswith("Good evening, Jad. You finished 1 task today.") and "Dentist at 09:00" in plain


def test_compose_uses_the_ai_and_cleans_up(ctx):
    setup_day(ctx)
    claude = FakeClaude(response(text("Good evening, Jad. Well done today.")))
    out = wrapup.compose(ctx, lambda **kw: Brain(ctx, client=claude, **kw))
    assert out == "Good evening, Jad. Well done today."
    assert "Renew car registration" in claude.requests[0]["messages"][-1]["content"][-1]["text"]
    assert not ctx.db.query("SELECT id FROM conversations WHERE id LIKE 'wrapup-%'")


def test_sent_once_in_the_evening(ctx):
    setup_day(ctx)
    ctx.settings.wrapup_time = "21:00"
    events = []
    ctx.notifier.subscribe(events.append)
    make = lambda **kw: Brain(ctx, client=FakeClaude(response(text("Evening!"))), **kw)  # noqa: E731
    day = datetime(2026, 10, 1, tzinfo=DUBAI)
    assert not wrapup.send_if_due(ctx, make, now=day.replace(hour=20, minute=59))
    assert wrapup.send_if_due(ctx, make, now=day.replace(hour=21, minute=0))
    assert not wrapup.send_if_due(ctx, make, now=day.replace(hour=22))
    assert events[-1] == {**events[-1], "kind": "wrapup", "message": "Evening!"}
    ctx.settings.wrapup_time = "off"
    assert not wrapup.due(ctx, day.replace(day=2, hour=22))


def test_completed_tasks_get_a_time_and_tool(ctx):
    load_all()
    REGISTRY["add_todo"].handler(ctx, {"task": "Call bank"})
    REGISTRY["complete_todo"].handler(ctx, {"id": 1})
    assert ctx.db.one("SELECT done_at FROM todos")["done_at"]
    assert "Finished today: Call bank" in REGISTRY["get_wrapup_data"].handler(ctx, {})
