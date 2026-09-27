from datetime import datetime, timedelta, timezone

import pytest

from jarvis import briefing
from jarvis.brain import Brain
from jarvis.tools import REGISTRY, load_all
from tests.conftest import FakeClaude, response, text

WEATHER = {"place": "Dubai, Dubai, United Arab Emirates", "unit": "°C", "temperature": 34.2, "feels_like": 38,
           "humidity": 50, "wind": 12, "summary": "clear sky",
           "days": [{"date": "2026-09-27", "summary": "clear sky", "low": 29, "high": 39, "rain_chance": 0}]}


@pytest.fixture(autouse=True)
def fresh_cache():
    briefing._cache.clear()
    yield
    briefing._cache.clear()


@pytest.fixture
def dubai(ctx, monkeypatch):
    ctx.settings.home_city = "Dubai"
    ctx.settings.timezone = "Asia/Dubai"
    ctx.settings.my_name = "Jad"
    monkeypatch.setattr("jarvis.tools.web.fetch_weather", lambda city, units="celsius": WEATHER)
    soon = datetime.now(timezone.utc) + timedelta(minutes=30)
    later = datetime.now(timezone.utc) + timedelta(days=2)
    for msg, when in (("Gym", soon), ("Dentist in two days", later)):
        ctx.db.execute("INSERT INTO reminders (message, due_at, created_at) VALUES (?, ?, 'x')",
                       (msg, when.isoformat(timespec="seconds")))
    for task, pr in (("Pay rent", "low"), ("Deploy Jarvis", "high")):
        ctx.db.execute("INSERT INTO todos (task, priority, created_at) VALUES (?, ?, 'x')", (task, pr))
    return ctx


def test_gather_and_text(dubai):
    facts = briefing.gather(dubai)
    assert facts["weather"]["place"].startswith("Dubai")
    # Only today's reminders (the one in two days is left out, unless "30 min from now" is tomorrow).
    assert [r["message"] for r in facts["reminders"]] in (["Gym"], [])
    assert [t["task"] for t in facts["tasks"]] == ["Deploy Jarvis", "Pay rent"]  # high priority first
    lines = briefing.as_text(facts)
    assert "34.2°C" in lines and "Deploy Jarvis (high priority)" in lines and "Dentist" not in lines


def test_compose_uses_ai_with_web_search_and_cleans_up(dubai):
    claude = FakeClaude(response(text("Good morning, Jad. Clear skies, 34 degrees.")))
    make = lambda **kw: Brain(dubai, client=claude, **kw)  # noqa: E731
    assert briefing.compose(dubai, make) == "Good morning, Jad. Clear skies, 34 degrees."
    req = claude.requests[0]
    prompt = req["messages"][0]["content"][-1]["text"]
    assert "Deploy Jarvis" in prompt and "UAE" in prompt and "headlines" in prompt
    assert [t.get("name") for t in req["tools"]] == ["web_search"]  # no other tools
    assert dubai.db.query("SELECT id FROM conversations") == []     # nothing left behind

    # Cached for 30 minutes...
    assert briefing.compose(dubai, make) == "Good morning, Jad. Clear skies, 34 degrees."
    assert len(claude.requests) == 1
    # ...unless a fresh one is asked for.
    claude.responses.append(response(text("Second edition.")))
    assert briefing.compose(dubai, make, fresh=True) == "Second edition."


def test_compose_falls_back_when_ai_fails(dubai):
    def broken(**kw):
        raise RuntimeError("GEMINI_API_KEY is not set")

    out = briefing.compose(dubai, broken)
    assert out.startswith("Good ") and "Jad" in out and "34°C" in out and "Deploy Jarvis" in out


def test_morning_schedule(dubai):
    tz = dubai.settings.tz
    day = datetime(2026, 9, 28, tzinfo=tz)
    dubai.settings.briefing_time = "07:30"
    assert not briefing.due(dubai, day.replace(hour=7, minute=10))   # too early
    assert briefing.due(dubai, day.replace(hour=7, minute=30))
    assert not briefing.due(dubai, day.replace(hour=13))             # the morning has passed
    dubai.settings.briefing_time = "off"
    assert not briefing.due(dubai, day.replace(hour=8))
    dubai.settings.briefing_time = "banana"
    assert not briefing.due(dubai, day.replace(hour=8))


def test_send_once_per_day_even_after_restart(dubai):
    events = []
    dubai.notifier.subscribe(events.append)
    dubai.settings.briefing_time = "07:30"
    claude = FakeClaude(response(text("Morning brief.")), response(text("Next day brief.")))
    make = lambda **kw: Brain(dubai, client=claude, **kw)  # noqa: E731
    morning = datetime(2026, 9, 28, 8, 0, tzinfo=dubai.settings.tz)
    assert briefing.send_if_due(dubai, make, morning)
    assert not briefing.send_if_due(dubai, make, morning.replace(minute=5))
    assert dubai.db.get_kv("last_briefing") == "2026-09-28"  # stored in the database: survives restarts
    assert briefing.send_if_due(dubai, make, morning + timedelta(days=1))
    assert [(e["kind"], e["message"]) for e in events] == [("briefing", "Morning brief."), ("briefing", "Next day brief.")]


def test_briefing_endpoint(dubai):
    from fastapi.testclient import TestClient

    from jarvis.server import create_app

    claude = FakeClaude(response(text("Here is your day.")))
    app = create_app(dubai, brain_factory=lambda **kw: Brain(dubai, client=claude, **kw))
    local = TestClient(app, base_url="http://localhost", client=("127.0.0.1", 5000))
    assert local.post("/api/briefing").json() == {"text": "Here is your day."}
    remote = TestClient(app, base_url="http://localhost", client=("203.0.113.9", 5000))
    assert remote.post("/api/briefing").status_code == 401


def test_briefing_tool(dubai):
    load_all()
    out = REGISTRY["get_briefing_data"].handler(dubai, {})
    assert "Weather in Dubai" in out and "Deploy Jarvis" in out
