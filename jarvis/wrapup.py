"""Jarvis's evening wrap-up: what you got done today, what's still open, and
what tomorrow holds, plus a gentle nudge about important tasks that have been
waiting for days. Sent every evening at WRAPUP_TIME (default 21:00).
"""

from __future__ import annotations

import logging
import time
from datetime import datetime, timedelta, timezone
from typing import Any, Callable

from jarvis.tools import Context

log = logging.getLogger("jarvis.wrapup")

STALE_DAYS = 3


def gather(ctx: Context, now: datetime | None = None) -> dict[str, Any]:
    s = ctx.settings
    now = (now or datetime.now(s.tz)).astimezone(s.tz)
    midnight = now.replace(hour=0, minute=0, second=0, microsecond=0)
    utc = lambda d: d.astimezone(timezone.utc).isoformat(timespec="seconds")  # noqa: E731
    tomorrow, after = midnight + timedelta(days=1), midnight + timedelta(days=2)
    facts: dict[str, Any] = {"name": s.my_name, "date": now.strftime("%A %d %B")}
    facts["done_today"] = [r["task"] for r in ctx.db.query(
        "SELECT task FROM todos WHERE done = 1 AND done_at >= ? ORDER BY done_at", (utc(midnight),))]
    facts["open"] = ctx.db.query(
        "SELECT id, task, due, priority, created_at FROM todos WHERE done = 0 "
        "ORDER BY CASE priority WHEN 'high' THEN 0 WHEN 'med' THEN 1 ELSE 2 END, id LIMIT 8")
    facts["open_count"] = int(ctx.db.one("SELECT COUNT(*) AS n FROM todos WHERE done = 0")["n"] or 0)
    # The nudge: important tasks that have been sitting there for days.
    facts["stale"] = [r["task"] for r in ctx.db.query(
        "SELECT task FROM todos WHERE done = 0 AND priority = 'high' AND created_at <= ? ORDER BY id LIMIT 3",
        (utc(now - timedelta(days=STALE_DAYS)),))]
    facts["tomorrow_reminders"] = [
        {"time": datetime.fromisoformat(r["due_at"]).astimezone(s.tz).strftime("%H:%M"), "message": r["message"]}
        for r in ctx.db.query("SELECT message, due_at FROM reminders WHERE status = 'pending' AND due_at >= ? "
                              "AND due_at < ? ORDER BY due_at LIMIT 10", (utc(tomorrow), utc(after)))]
    if s.calendar_urls:
        try:
            from jarvis import agenda

            facts["tomorrow_events"] = [
                {"time": "all day" if e["all_day"] else datetime.fromisoformat(e["start"]).strftime("%H:%M"),
                 "title": e["title"]}
                for e in agenda.events_between(ctx, tomorrow, after)]
        except Exception:
            log.info("Calendar unavailable for the wrap-up", exc_info=True)
    return facts


def as_text(facts: dict[str, Any]) -> str:
    lines = [f"Today: {facts['date']}."]
    lines.append("Finished today: " + ("; ".join(facts["done_today"]) or "nothing ticked off."))
    if facts["open"]:
        lines.append(f"Still open ({facts['open_count']}): " + "; ".join(
            f"{t['task']} ({t['priority'] or 'med'})" for t in facts["open"]))
    else:
        lines.append("Still open: nothing. The list is clear.")
    if facts["stale"]:
        lines.append(f"Important tasks waiting {STALE_DAYS}+ days: " + "; ".join(facts["stale"]))
    if "tomorrow_events" in facts:
        lines.append("Calendar tomorrow: " + ("; ".join(f"{e['time']} {e['title']}" for e in facts["tomorrow_events"])
                                              or "nothing."))
    lines.append("Reminders tomorrow: " + ("; ".join(f"{r['time']} {r['message']}" for r in facts["tomorrow_reminders"])
                                           or "none."))
    return "\n".join(lines)


def fallback(facts: dict[str, Any]) -> str:
    done = len(facts["done_today"])
    bits = [f"Good evening, {facts['name']}. You finished {done} task{'s' if done != 1 else ''} today."]
    bits.append(f"{facts['open_count']} still open." if facts["open_count"] else "Your list is clear.")
    if facts["stale"]:
        bits.append(f"{facts['stale'][0]} has been waiting a few days; maybe tomorrow?")
    first = (facts.get("tomorrow_events") or facts["tomorrow_reminders"] or [None])[0]
    if first:
        bits.append(f"Tomorrow starts with {first.get('title') or first.get('message')} at {first['time']}.")
    return " ".join(bits)


def compose(ctx: Context, make_brain: Callable[..., Any], now: datetime | None = None) -> str:
    facts = gather(ctx, now)
    prompt = f"""Give me my evening wrap-up, written to be read aloud: 80-130 words, warm and calm,
in your JARVIS voice, no lists, headings or emoji. Open with "Good evening, {facts['name']}." Cover:
what I finished today (a little praise if it's earned), what's still open, a gentle nudge about any
important task that has been waiting for days (kind, not nagging), then what tomorrow holds.
Close with one short line. Skip anything that's missing.

The facts:
{as_text(facts)}"""
    conv = f"wrapup-{int(time.time() * 1000)}"
    try:
        brain = make_brain(conversation_id=conv, tools=[], web_search=False, remember_facts=False, effort="low")
        return brain.chat(prompt).text.strip()
    except Exception:
        log.exception("Couldn't compose the wrap-up with the AI; using the plain version")
        return fallback(facts)
    finally:
        ctx.db.delete_conversation(conv)


def due(ctx: Context, now: datetime | None = None) -> bool:
    setting = ctx.settings.wrapup_time
    if not setting or setting == "off":
        return False
    try:
        hour, minute = (int(x) for x in setting.split(":"))
    except ValueError:
        return False
    now = now or datetime.now(ctx.settings.tz)
    if (now.hour, now.minute) < (hour, minute):
        return False  # (until midnight: a server that wakes up late still sends it)
    return ctx.db.get_kv("last_wrapup") != now.date().isoformat()


def send_if_due(ctx: Context, make_brain: Callable[..., Any], now: datetime | None = None) -> bool:
    now = now or datetime.now(ctx.settings.tz)
    if not due(ctx, now):
        return False
    ctx.db.set_kv("last_wrapup", now.date().isoformat())  # claim first: never twice
    ctx.notifier.publish("wrapup", compose(ctx, make_brain, now))
    return True
