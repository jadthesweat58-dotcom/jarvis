"""Reminders and timers. The background loop in jarvis/scheduler.py fires them."""

from __future__ import annotations

import json
from datetime import datetime, timedelta, timezone

from jarvis.db import utcnow
from jarvis.tools import Context, ToolError, tool

CHANNELS = ["app", "call", "sms"]


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
    },
    ["message"],
)
def set_reminder(ctx: Context, args: dict) -> str:
    when = parse_when(ctx, args)
    channels = [c for c in (args.get("notify_by") or ["app"]) if c in CHANNELS] or ["app"]
    if any(c in ("call", "sms") for c in channels) and not (
        ctx.settings.twilio_enabled and ctx.settings.my_phone_number
    ):
        raise ToolError("Phone alerts aren't set up (Twilio + MY_PHONE_NUMBER needed). Use 'app' instead.")
    rid = ctx.db.execute(
        "INSERT INTO reminders (message, due_at, notify_by, created_at) VALUES (?, ?, ?, ?)",
        (args["message"].strip(), when.isoformat(timespec="seconds"), json.dumps(channels), utcnow()),
    )
    return f"Reminder #{rid} set for {to_local(ctx, when.isoformat())} via {', '.join(channels)}."


@tool("list_reminders", "List upcoming reminders and timers.")
def list_reminders(ctx: Context, args: dict) -> str:
    rows = ctx.db.query("SELECT * FROM reminders WHERE status = 'pending' ORDER BY due_at")
    if not rows:
        return "No upcoming reminders."
    return "\n".join(
        f"#{r['id']} {to_local(ctx, r['due_at'])}: {r['message']} ({', '.join(json.loads(r['notify_by']))})"
        for r in rows
    )


@tool("cancel_reminder", "Cancel a reminder by id.", {"id": {"type": "integer"}}, ["id"])
def cancel_reminder(ctx: Context, args: dict) -> str:
    changed = ctx.db.execute(
        "UPDATE reminders SET status = 'cancelled' WHERE id = ? AND status = 'pending'", (args["id"],)
    )
    if not changed:
        raise ToolError(f"No upcoming reminder #{args['id']}.")
    return f"Cancelled reminder #{args['id']}."
