import json
from datetime import datetime, timedelta, timezone

import pytest

from jarvis.scheduler import fire_due_reminders
from jarvis.tools import REGISTRY, ToolError, available_tools, load_all

load_all()


def run(ctx, tool_name, **args):
    return REGISTRY[tool_name].handler(ctx, args)


def test_memory_roundtrip(ctx):
    assert "Saved fact #1" in run(ctx, "remember_fact", fact="My favourite colour is blue", category="preferences")
    assert "blue" in run(ctx, "recall_facts", query="colour")
    assert "No matching" in run(ctx, "recall_facts", query="pizza")
    run(ctx, "forget_fact", id=1)
    assert "No matching" in run(ctx, "recall_facts")
    with pytest.raises(ToolError):
        run(ctx, "forget_fact", id=99)


def test_notes_and_todos(ctx):
    run(ctx, "add_note", title="Gift ideas", body="Watch for Pepper")
    assert "Pepper" in run(ctx, "search_notes", query="watch")
    run(ctx, "add_todo", task="Fix the suit", due="2026-10-01")
    run(ctx, "add_todo", task="Call Rhodey")
    assert "Fix the suit (due 2026-10-01)" in run(ctx, "list_todos")
    run(ctx, "complete_todo", id=1)
    assert "Fix the suit" not in run(ctx, "list_todos")
    assert "[x] #1 Fix the suit" in run(ctx, "list_todos", include_done=True)


def test_reminder_fires_and_notifies(ctx):
    events = []
    ctx.notifier.subscribe(events.append)
    out = run(ctx, "set_reminder", message="Take a break", in_minutes=5)
    assert "Reminder #1" in out
    assert "Take a break" in run(ctx, "list_reminders")
    assert fire_due_reminders(ctx) == 0  # not due yet
    past = (datetime.now(timezone.utc) - timedelta(seconds=1)).isoformat(timespec="seconds")
    ctx.db.execute("UPDATE reminders SET due_at = ?", (past,))
    assert fire_due_reminders(ctx) == 1
    assert events == [{"kind": "reminder", "message": "Reminder: Take a break", "id": 1}]
    assert fire_due_reminders(ctx) == 0  # never fires twice


def test_reminder_at_local_time_and_validation(ctx):
    ctx.settings.timezone = "America/New_York"
    tomorrow = (datetime.now(ctx.settings.tz) + timedelta(days=1)).replace(hour=9, minute=0, second=0, microsecond=0)
    run(ctx, "set_reminder", message="Standup", at=tomorrow.strftime("%Y-%m-%dT%H:%M"))
    stored = ctx.db.one("SELECT due_at FROM reminders")["due_at"]
    assert datetime.fromisoformat(stored) == tomorrow.astimezone(timezone.utc)
    with pytest.raises(ToolError):
        run(ctx, "set_reminder", message="x", at="2001-01-01T09:00")
    with pytest.raises(ToolError):
        run(ctx, "set_reminder", message="x")
    with pytest.raises(ToolError, match="Phone alerts"):
        run(ctx, "set_reminder", message="x", in_minutes=1, notify_by=["call"])


def test_cancel_reminder(ctx):
    run(ctx, "set_reminder", message="x", in_minutes=10)
    run(ctx, "cancel_reminder", id=1)
    assert run(ctx, "list_reminders") == "No upcoming reminders."
    with pytest.raises(ToolError):
        run(ctx, "cancel_reminder", id=1)


def test_weather_uses_open_meteo(ctx, monkeypatch):
    class Resp:
        def __init__(self, data):
            self.data = data

        def raise_for_status(self):
            pass

        def json(self):
            return self.data

    def fake_get(url, params, timeout):
        if "geocoding" in url:
            return Resp({"results": [
                {"name": "Paris", "country": "United States", "country_code": "US", "admin1": "Texas", "latitude": 1, "longitude": 2},
                {"name": "Paris", "country": "France", "country_code": "FR", "admin1": "Île-de-France", "latitude": 48.8, "longitude": 2.3},
            ]})
        assert params["latitude"] == 48.8
        return Resp({
            "current": {"temperature_2m": 18, "apparent_temperature": 17, "relative_humidity_2m": 60,
                        "weather_code": 2, "wind_speed_10m": 10},
            "daily": {"time": ["2026-09-26"], "weather_code": [61], "temperature_2m_min": [12],
                      "temperature_2m_max": [19], "precipitation_probability_max": [70]},
        })

    monkeypatch.setattr("jarvis.tools.web.httpx.get", fake_get)
    out = run(ctx, "get_weather", location="Paris, France")
    assert "Paris, Île-de-France, France" in out and "partly cloudy" in out and "light rain" in out
    with pytest.raises(ToolError, match="HOME_CITY"):
        run(ctx, "get_weather")


def test_tool_availability_depends_on_setup(ctx, phone_ctx):
    names = {t.name for t in available_tools(ctx.settings)}
    assert "run_command" not in names  # cloud mode
    assert "call_me" in names  # phone_ctx configured Twilio on the same settings
    ctx.settings.twilio_account_sid = ""
    ctx.settings.mode = "local"
    names = {t.name for t in available_tools(ctx.settings)}
    assert "run_command" in names and "call_me" not in names


def test_contacts_and_calls(phone_ctx, twilio):
    ctx = phone_ctx
    with pytest.raises(ToolError, match="country code"):
        run(ctx, "add_contact", name="Mom", phone="555-1234")
    run(ctx, "add_contact", name="Mom", phone="+1 (555) 123-4567", relationship="mother")
    assert "Mom: +15551234567 (mother)" in run(ctx, "list_contacts")
    assert REGISTRY["call_contact"].requires_approval(ctx, {"who": "Mom", "message": "hi"})
    summary = REGISTRY["call_contact"].describe(ctx, {"who": "mom", "message": "Dinner at 7?"})
    assert "+15551234567" in summary and "Dinner at 7?" in summary

    run(ctx, "call_contact", who="Mom", message="Dinner at 7?")
    call = twilio.calls_made[-1]
    assert call["to"] == "+15551234567" and call["from_"] == "+15550000000"
    assert "Jarvis, Tony's AI assistant" in call["twiml"] and "Dinner at 7?" in call["twiml"]

    run(ctx, "call_me", message="Wake up", conversation=True)
    assert twilio.calls_made[-1]["to"] == "+15551112222"
    assert "twiml" in twilio.calls_made[-1]  # no PUBLIC_BASE_URL -> one-way call

    ctx.settings.public_base_url = "https://jarvis.example.com"
    run(ctx, "call_me", message="Let's talk", conversation=True)
    last = twilio.calls_made[-1]
    assert last["url"] == "https://jarvis.example.com/twilio/voice?call_id=3"
    assert last["status_callback"].startswith("https://jarvis.example.com/twilio/status")

    run(ctx, "text_contact", who="Mom", message="Running late")
    run(ctx, "text_me", message="Note to self")
    assert [t["to"] for t in twilio.texts_sent] == ["+15551234567", "+15551112222"]
    with pytest.raises(ToolError, match="No contact"):
        run(ctx, "text_contact", who="Nobody", message="hi")


def test_computer_tools_stay_inside_root(ctx, tmp_path):
    (tmp_path / "hello.txt").write_text("hi there")
    (tmp_path / "docs").mkdir()
    assert "[dir] docs" in run(ctx, "list_files") and "hello.txt" in run(ctx, "list_files")
    assert run(ctx, "read_file", path="hello.txt") == "hi there"
    with pytest.raises(ToolError, match="only access files inside"):
        run(ctx, "read_file", path="../../etc/passwd")
    run(ctx, "write_file", path="docs/new.txt", content="made by jarvis")
    assert (tmp_path / "docs" / "new.txt").read_text() == "made by jarvis"
    assert "Exit code 0" in run(ctx, "run_command", command="echo jarvis-ok") and \
        "jarvis-ok" in run(ctx, "run_command", command="echo jarvis-ok")
    assert REGISTRY["run_command"].requires_approval(ctx, {"command": "ls"})
    with pytest.raises(ToolError):
        run(ctx, "open_app", name="calc; rm -rf /")
