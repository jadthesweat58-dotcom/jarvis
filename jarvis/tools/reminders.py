"""Reminders and timers. The background loop in jarvis/scheduler.py fires them."""

from __future__ import annotations

import calendar
import json
from datetime import datetime, timedelta, timezone
from zoneinfo import ZoneInfo

from jarvis.db import utcnow
from jarvis.tools import Context, ToolError, tool

CHANNELS = ["app", "call", "sms"]
REPEATS = ["daily", "weekdays", "weekly", "monthly"]
REPEAT_WORDS = {"daily": "every day", "weekdays": "every weekday", "weekly": "every week", "monthly": "every month"}


def repeat_rule(rule: str | None, first: datetime, tz: ZoneInfo) -> str | None:
    """The stored rule. Monthly remembers its day, so the 31st stays the 31st
    (or the month's last day) instead of drifting after a short month."""
    if not rule:
        return None
    if rule not in REPEATS:
        raise ToolError(f"repeat must be one of {', '.join(REPEATS)}.")
    return f"monthly:{first.astimezone(tz).day}" if rule == "monthly" else rule


def describe_repeat(rule: str | None) -> str:
    return REPEAT_WORDS.get((rule or "").split(":")[0], "")


def next_due(due_utc: str, rule: str, tz: ZoneInfo, now: datetime | None = None) -> str:
    """The next time a repeating reminder is due after ``now`` (UTC ISO), keeping
    the same local clock time across daylight-saving changes. Occurrences missed
    while the server was asleep are skipped, not fired in a burst."""
    now = now or datetime.now(timezone.utc)
    local = datetime.fromisoformat(due_utc).astimezone(tz).replace(tzinfo=None)  # wall-clock time
    kind, _, anchor = rule.partition(":")
    for _ in range(5000):
        if kind == "daily":
            local += timedelta(days=1)
        elif kind == "weekdays":
            local += timedelta(days=1)
            while local.weekday() >= 5:  # skip Saturday and Sunday
                local += timedelta(days=1)
        elif kind == "weekly":
            local += timedelta(weeks=1)
        elif kind == "monthly":
            year, month = (local.year + 1, 1) if local.month == 12 else (local.year, local.month + 1)
            day = min(int(anchor or local.day), calendar.monthrange(year, month)[1])
            local = local.replace(year=year, month=month, day=day)
        else:
            raise ValueError(f"Unknown repeat rule {rule!r}")
        when = local.replace(tzinfo=tz).astimezone(timezone.utc)
        if when > now:
            return when.isoformat(timespec="seconds")
    raise ValueError("Couldn't find the next occurrence.")


def parse_when(ctx: Context, args: dict) -> datetime:
    """Turn 'at' (local time) or 'in_minutes' into an aware UTC datetime."""
    if args.get("in_minutes") is not None:
        minutes = float(args["in_minutes"])
        if minutes <= 0:
            raise ToolError("in_minutes must be positive.")
        return datetime.now(timezone.utc) + timedelta(minutes=minutes)
    if args.get("at"):
        try:
            when = datetime.fromisoformat(str(args["at"]).strip())
        except ValueError as exc:
            raise ToolError("'at' must look like 2026-09-27T09:00.") from exc
        if when.tzinfo is None:
            when = when.replace(tzinfo=ctx.settings.tz)
        when = when.astimezone(timezone.utc)
        if when <= datetime.now(timezone.utc):
            raise ToolError("That time is in the past.")
        return when
    raise ToolError("Give either 'at' or 'in_minutes'.")


def to_local(ctx: Context, iso_utc: str) -> str:
    return datetime.fromisoformat(iso_utc).astimezone(ctx.settings.tz).strftime("%a %d %b %Y %H:%M")


@tool(
    "set_reminder",
    "Set a reminder or timer. Jarvis will alert the user at that time. Use "
    "in_minutes for timers / relative times ('in 20 minutes'), or 'at' for a "
    "clock time in the user's local timezone.",
    {
        "message": {"type": "string", "description": "What to remind the user about."},
        "at": {"type": "string", "description": "Local date-time, ISO format: 2026-09-27T09:00"},
        "in_minutes": {"type": "number", "description": "Minutes from now (can be fractional)."},
        "notify_by": {
            "type": "array",
            "items": {"type": "string", "enum": CHANNELS},
            "description": "How to alert: app (on screen + spoken), call (phone the user), "
            "sms (text the user). Default: app.",
        },
        "repeat": {
            "type": "string",
            "enum": REPEATS,
            "description": "Make it repeat (e.g. 'every weekday at 8'). weekdays = Monday to Friday. "
            "'at' is then the first time. Leave out for a one-off reminder.",
        },
    },
    ["message"],
)
def set_reminder(ctx: Context, args: dict) -> str:
    when = parse_when(ctx, args)
    rule = repeat_rule(args.get("repeat"), when, ctx.settings.tz)
    channels = [c for c in (args.get("notify_by") or ["app"]) if c in CHANNELS] or ["app"]
    if any(c in ("call", "sms") for c in channels) and not (
        ctx.settings.twilio_enabled and ctx.settings.my_phone_number
    ):
        raise ToolError("Phone alerts aren't set up (Twilio + MY_PHONE_NUMBER needed). Use 'app' instead.")
    rid = ctx.db.execute(
        "INSERT INTO reminders (message, due_at, notify_by, repeat_rule, created_at) VALUES (?, ?, ?, ?, ?)",
        (args["message"].strip(), when.isoformat(timespec="seconds"), json.dumps(channels), rule, utcnow()),
    )
    repeats = f", repeating {describe_repeat(rule)}" if rule else ""
    return f"Reminder #{rid} set for {to_local(ctx, when.isoformat())}{repeats} via {', '.join(channels)}."


@tool("list_reminders", "List upcoming reminders and timers.")
def list_reminders(ctx: Context, args: dict) -> str:
    rows = ctx.db.query("SELECT * FROM reminders WHERE status = 'pending' ORDER BY due_at")
    if not rows:
        return "No upcoming reminders."
    return "\n".join(
        f"#{r['id']} {to_local(ctx, r['due_at'])}: {r['message']} ({', '.join(json.loads(r['notify_by']))}"
        + (f"; repeats {describe_repeat(r.get('repeat_rule'))})" if r.get("repeat_rule") else ")")
        for r in rows
    )


@tool("cancel_reminder", "Cancel a reminder by id (for a repeating one, this stops every future repeat).",
      {"id": {"type": "integer"}}, ["id"])
def cancel_reminder(ctx: Context, args: dict) -> str:
    changed = ctx.db.execute(
        "UPDATE reminders SET status = 'cancelled' WHERE id = ? AND status = 'pending'", (args["id"],)
    )
    if not changed:
        raise ToolError(f"No upcoming reminder #{args['id']}.")
    return f"Cancelled reminder #{args['id']}."
