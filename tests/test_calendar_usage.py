from datetime import datetime, timedelta
from types import SimpleNamespace
from zoneinfo import ZoneInfo

import pytest
from fastapi.testclient import TestClient

from jarvis import agenda, briefing, usage
from jarvis.brain import Brain
from jarvis.server import create_app
from jarvis.voice import ElevenLabsVoice
from tests.conftest import FakeClaude, response, text

ICS = """BEGIN:VCALENDAR
VERSION:2.0
PRODID:-//Test//EN
X-WR-TIMEZONE:Asia/Dubai
BEGIN:VEVENT
UID:standup@test
DTSTART;TZID=Asia/Dubai:20260928T093000
DTEND;TZID=Asia/Dubai:20260928T094500
RRULE:FREQ=WEEKLY;BYDAY=MO,WE
SUMMARY:Team standup
LOCATION:Zoom
END:VEVENT
BEGIN:VEVENT
UID:bday@test
DTSTART;VALUE=DATE:20260930
DTEND;VALUE=DATE:20261001
SUMMARY:Sara's birthday
END:VEVENT
BEGIN:VEVENT
UID:cancelled@test
DTSTART:20260930T100000Z
DTEND:20260930T110000Z
STATUS:CANCELLED
SUMMARY:Cancelled thing
END:VEVENT
END:VCALENDAR
"""
DUBAI = ZoneInfo("Asia/Dubai")


class FakeHTTP:
    def __init__(self, body):
        self.body, self.urls = body, []

    def get(self, url, timeout=None, follow_redirects=None):
        self.urls.append(url)
        return SimpleNamespace(content=self.body.encode(), raise_for_status=lambda: None)


@pytest.fixture
def cal(ctx):
    agenda._cache.clear()
    ctx.settings.timezone = "Asia/Dubai"
    ctx.settings.calendar_ics_url = "webcal://calendar.example/private-abc/basic.ics"
    yield ctx
    agenda._cache.clear()


def test_expands_repeating_and_all_day_events(cal):
    http = FakeHTTP(ICS)
    start = datetime(2026, 9, 28, tzinfo=DUBAI)
    events = agenda.events_between(cal, start, start + timedelta(days=3), client=http)
    assert [(e["title"], e["start"][:16], e["all_day"]) for e in events] == [
        ("Team standup", "2026-09-28T09:30", False),
        ("Sara's birthday", "2026-09-30T00:00", True),
        ("Team standup", "2026-09-30T09:30", False),
    ]
    assert http.urls == ["https://calendar.example/private-abc/basic.ics"]
    agenda.events_between(cal, start, start + timedelta(days=1), client=http)
    assert len(http.urls) == 1  # cached
    assert agenda.describe(events[0]) == "Mon 28 Sep 09:30–09:45: Team standup (Zoom)"
    assert agenda.describe(events[1]) == "Wed 30 Sep, all day: Sara's birthday"


def test_broken_calendar_is_skipped(cal):
    assert agenda.events_between(cal, datetime(2026, 9, 28, tzinfo=DUBAI), datetime(2026, 9, 29, tzinfo=DUBAI),
                                 client=FakeHTTP("not a calendar")) == []


def test_calendar_in_timeline_and_briefing(cal, monkeypatch):
    now = datetime.now(DUBAI)
    later = now + timedelta(hours=1)
    monkeypatch.setattr(agenda, "today", lambda ctx, client=None: [
        {"title": "Dentist", "location": "", "all_day": False, "start": later.isoformat(),
         "end": (later + timedelta(minutes=30)).isoformat()}])
    app = create_app(cal, brain_factory=lambda **kw: Brain(cal, client=FakeClaude(), **kw))
    client = TestClient(app, base_url="http://localhost", client=("127.0.0.1", 5000))
    timeline = client.get("/api/dashboard").json()["timeline"]
    assert timeline[0]["kind"] == "event" and timeline[0]["message"] == "Dentist"
    assert timeline[0]["time_local"] == later.strftime("%H:%M") and timeline[0]["status"] == "pending"
    assert client.get("/api/status").json()["calendar"] is True
    facts = briefing.gather(cal)
    assert facts["events"][0]["title"] == "Dentist"
    assert f"Calendar today: {later:%H:%M} Dentist" in briefing.as_text(facts)
    assert "On your calendar: Dentist" in briefing.fallback(facts)


# ---------------------------------------------------------------- usage meter
def test_brain_records_tokens(ctx):
    reply = response(text("Hi."))
    reply.usage = SimpleNamespace(input_tokens=1200, output_tokens=80, cache_read_input_tokens=300)
    Brain(ctx, client=FakeClaude(reply)).chat("hello")
    today = usage.summary(ctx)["today"]
    assert today == {"ai_calls": 1, "ai_tokens_in": 1500, "ai_tokens_out": 80, "tts_chars": 0}


def test_voice_characters_count_towards_quota(ctx):
    ctx.settings.elevenlabs_api_key, ctx.settings.elevenlabs_voice_id = "k", "v"
    http = SimpleNamespace(post=lambda *a, **kw: SimpleNamespace(status_code=200, content=b"mp3"))
    voice = ElevenLabsVoice(ctx.settings, client=http, on_usage=lambda n: usage.record(ctx, {"tts_chars": n}))
    voice.speak("Good morning, Tony.")
    voice.speak("Good morning, Tony.")  # cached: free
    voice.speak("Another line")
    summary = usage.summary(ctx)
    assert summary["month"]["tts_chars"] == len("Good morning, Tony.") + len("Another line")
    assert summary["tts_left"] == ctx.settings.elevenlabs_monthly_chars - summary["month"]["tts_chars"]


def test_usage_and_export_endpoints(ctx):
    ctx.db.execute("INSERT INTO facts (fact, category, created_at) VALUES ('Likes karak tea', 'food', 'x')")
    ctx.db.set_kv("vapid_private_key", "SECRET-KEY")
    usage.record(ctx, {"ai_calls": 3})
    app = create_app(ctx, brain_factory=lambda **kw: Brain(ctx, client=FakeClaude(), **kw))
    client = TestClient(app, base_url="http://localhost", client=("127.0.0.1", 5000))
    assert client.get("/api/usage").json()["today"]["ai_calls"] == 3
    out = client.get("/api/export")
    assert "attachment" in out.headers["content-disposition"]
    data = out.json()
    assert data["facts"][0]["fact"] == "Likes karak tea" and "SECRET-KEY" not in out.text
    assert set(data) >= {"facts", "notes", "todos", "reminders", "contacts", "phone_calls"}
