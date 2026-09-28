from datetime import datetime, timedelta, timezone
from zoneinfo import ZoneInfo

from jarvis.scheduler import fire_due_reminders
from jarvis.tools import REGISTRY, load_all
from jarvis.tools.reminders import next_due

UTC = timezone.utc


def iso(dt):
    return dt.astimezone(UTC).isoformat(timespec="seconds")


def test_daily_weekly_and_weekdays():
    tz = ZoneInfo("Asia/Dubai")
    friday_8am = datetime(2026, 10, 2, 8, 0, tzinfo=tz)  # a Friday
    now = friday_8am.astimezone(UTC) + timedelta(seconds=1)
    assert next_due(iso(friday_8am), "daily", tz, now) == iso(datetime(2026, 10, 3, 8, 0, tzinfo=tz))
    assert next_due(iso(friday_8am), "weekly", tz, now) == iso(datetime(2026, 10, 9, 8, 0, tzinfo=tz))
    # Weekdays skip Saturday and Sunday.
    assert next_due(iso(friday_8am), "weekdays", tz, now) == iso(datetime(2026, 10, 5, 8, 0, tzinfo=tz))


def test_monthly_keeps_its_day_after_short_months():
    tz = ZoneInfo("UTC")
    jan31 = datetime(2027, 1, 31, 9, 0, tzinfo=tz)
    feb = next_due(iso(jan31), "monthly:31", tz, jan31 + timedelta(seconds=1))
    assert feb == iso(datetime(2027, 2, 28, 9, 0, tzinfo=tz))
    march = next_due(feb, "monthly:31", tz, datetime.fromisoformat(feb) + timedelta(seconds=1))
    assert march == iso(datetime(2027, 3, 31, 9, 0, tzinfo=tz))  # back to the 31st, not stuck on the 28th


def test_keeps_local_time_across_daylight_saving():
    tz = ZoneInfo("America/New_York")
    before = datetime(2026, 10, 31, 9, 0, tzinfo=tz)  # clocks go back on 1 November
    after = next_due(iso(before), "daily", tz, before + timedelta(seconds=1))
    assert datetime.fromisoformat(after).astimezone(tz).hour == 9
    assert iso(before)[11:13] == "13" and after[11:13] == "14"  # same local time, different UTC


def test_missed_repeats_are_skipped_not_fired_in_a_burst():
    tz = ZoneInfo("UTC")
    now = datetime.now(UTC)
    ten_days_ago = now - timedelta(days=10, minutes=5)
    nxt = datetime.fromisoformat(next_due(iso(ten_days_ago), "daily", tz, now))
    assert now < nxt <= now + timedelta(days=1)


def test_repeating_reminder_fires_once_then_moves_on(ctx):
    events = []
    ctx.notifier.subscribe(events.append)
    due = (datetime.now(UTC) - timedelta(seconds=5)).replace(microsecond=0)
    rid = ctx.db.execute(
        "INSERT INTO reminders (message, due_at, repeat_rule, created_at) VALUES ('Stretch', ?, 'daily', 'x')",
        (iso(due),))
    assert fire_due_reminders(ctx) == 1
    assert fire_due_reminders(ctx) == 0  # not twice
    row = ctx.db.one("SELECT * FROM reminders WHERE id = ?", (rid,))
    assert row["status"] == "pending"
    assert datetime.fromisoformat(row["due_at"]) - due == timedelta(days=1)
    assert [e["message"] for e in events if e["kind"] == "reminder"] == ["Reminder: Stretch"]


def test_set_and_list_repeating_reminder(ctx):
    load_all()
    out = REGISTRY["set_reminder"].handler(ctx, {"message": "Standup", "in_minutes": 60, "repeat": "weekdays"})
    assert "repeating every weekday" in out
    assert "repeats every weekday" in REGISTRY["list_reminders"].handler(ctx, {})
    out = REGISTRY["set_reminder"].handler(ctx, {"message": "Rent", "in_minutes": 60, "repeat": "monthly"})
    rule = ctx.db.one("SELECT repeat_rule FROM reminders WHERE message = 'Rent'")["repeat_rule"]
    assert rule.startswith("monthly:")
    # Cancelling stops the whole series.
    rid = ctx.db.one("SELECT id FROM reminders WHERE message = 'Standup'")["id"]
    REGISTRY["cancel_reminder"].handler(ctx, {"id": rid})
    assert ctx.db.one("SELECT status FROM reminders WHERE id = ?", (rid,))["status"] == "cancelled"
