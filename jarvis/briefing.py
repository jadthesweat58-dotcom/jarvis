"""Jarvis's daily briefing: weather, today's reminders and tasks, and top news.

``gather`` collects the facts; ``compose`` has the AI turn them into a short
spoken briefing (adding news with its web search), with a plain fallback if the
AI can't be reached. The scheduler sends one every morning at BRIEFING_TIME.
"""

from __future__ import annotations

import logging
import threading
import time
from datetime import datetime, timezone
from typing import Any, Callable

from jarvis.tools import Context

log = logging.getLogger("jarvis.briefing")

CACHE_SECONDS = 30 * 60
_cache: dict[int, tuple[float, str]] = {}   # id(ctx) -> (made at, text)
_lock = threading.Lock()


def gather(ctx: Context) -> dict[str, Any]:
    s = ctx.settings
    now = datetime.now(s.tz)
    facts: dict[str, Any] = {"name": s.my_name, "date": now.strftime("%A %d %B %Y"),
                             "time": now.strftime("%H:%M"), "city": s.home_city}
    if s.home_city:
        try:
            from jarvis.tools.web import fetch_weather

            facts["weather"] = fetch_weather(s.home_city)
        except Exception:
            log.info("Weather unavailable for the briefing", exc_info=True)
    midnight = now.replace(hour=0, minute=0, second=0, microsecond=0)
    tomorrow = midnight.timestamp() + 86400
    reminders = ctx.db.query(
        "SELECT message, due_at FROM reminders WHERE status = 'pending' AND due_at >= ? ORDER BY due_at LIMIT 20",
        (now.astimezone(timezone.utc).isoformat(timespec="seconds"),))
    facts["reminders"] = [
        {"time": datetime.fromisoformat(r["due_at"]).astimezone(s.tz).strftime("%H:%M"), "message": r["message"]}
        for r in reminders if datetime.fromisoformat(r["due_at"]).timestamp() < tomorrow
    ]
    facts["tasks"] = ctx.db.query(
        "SELECT task, due, priority FROM todos WHERE done = 0 "
        "ORDER BY CASE priority WHEN 'high' THEN 0 WHEN 'med' THEN 1 ELSE 2 END, id LIMIT 5")
    facts["open_tasks"] = int(ctx.db.one("SELECT COUNT(*) AS n FROM todos WHERE done = 0")["n"] or 0)
    if s.gmail_configured:
        try:
            from jarvis import gmail

            if gmail.connected_email(ctx):
                mail = gmail.search(ctx, "is:unread is:important newer_than:1d", 5)
                facts["email"] = [{"from": gmail.sender_name(m["from"]), "subject": m["subject"]} for m in mail]
        except Exception:
            log.info("Gmail unavailable for the briefing", exc_info=True)
    if s.calendar_urls:
        try:
            from jarvis import agenda

            facts["events"] = [
                {"time": "all day" if e["all_day"] else datetime.fromisoformat(e["start"]).strftime("%H:%M"),
                 "title": e["title"], "location": e["location"]}
                for e in agenda.today(ctx)
            ]
        except Exception:
            log.info("Calendar unavailable for the briefing", exc_info=True)
    return facts


def as_text(facts: dict[str, Any]) -> str:
    """The gathered facts as plain lines (for the AI, or for the chat tool)."""
    lines = [f"Date: {facts['date']}, {facts['time']} local time."]
    w = facts.get("weather")
    if w:
        today = w["days"][0] if w.get("days") else {}
        lines.append(f"Weather in {w['place']}: {w['temperature']}{w['unit']} now, {w['summary']}"
                     + (f"; today {today.get('low')}–{today.get('high')}{w['unit']}, "
                        f"{today.get('rain_chance')}% chance of rain." if today else "."))
    elif facts.get("city"):
        lines.append("Weather: unavailable right now.")
    if "events" in facts:
        lines.append("Calendar today: " + ("; ".join(
            f"{e['time']} {e['title']}" + (f" at {e['location']}" if e["location"] else "")
            for e in facts["events"]) or "nothing."))
    if "email" in facts:
        lines.append("Important unread email: " + ("; ".join(f"{m['from']}: {m['subject']}" for m in facts["email"])
                                                  or "none."))
    if facts["reminders"]:
        lines.append("Reminders today: " + "; ".join(f"{r['time']} {r['message']}" for r in facts["reminders"]))
    else:
        lines.append("Reminders today: none.")
    if facts["tasks"]:
        tasks = "; ".join(f"{t['task']} ({t['priority'] or 'med'} priority"
                          + (f", due {t['due']})" if t.get("due") else ")") for t in facts["tasks"])
        lines.append(f"Open tasks ({facts['open_tasks']} total): {tasks}")
    else:
        lines.append("Open tasks: none.")
    return "\n".join(lines)


def fallback(facts: dict[str, Any]) -> str:
    """A plain briefing when the AI can't be reached."""
    part = _part_of_day(facts["time"])
    bits = [f"Good {part}, {facts['name']}. It's {facts['date']}."]
    w = facts.get("weather")
    if w:
        bits.append(f"In {w['place'].split(',')[0]} it's {round(w['temperature'])}{w['unit']} and {w['summary']}.")
    events = facts.get("events") or []
    if events:
        bits.append(f"On your calendar: {events[0]['title']} ({events[0]['time']})"
                    + (f" and {len(events) - 1} more." if len(events) > 1 else "."))
    n = len(facts["reminders"])
    bits.append(f"You have {n} reminder{'s' if n != 1 else ''} today" + (
        f", starting with {facts['reminders'][0]['message']} at {facts['reminders'][0]['time']}." if n else "."))
    t = facts["open_tasks"]
    bits.append(f"And {t} open task{'s' if t != 1 else ''}" + (f"; top of the list: {facts['tasks'][0]['task']}." if t else "."))
    return " ".join(bits)


def _part_of_day(hhmm: str) -> str:
    hour = int(hhmm.split(":")[0])
    return "morning" if hour < 12 else "afternoon" if hour < 18 else "evening"


def compose(ctx: Context, make_brain: Callable[..., Any], fresh: bool = False) -> str:
    """A short spoken briefing. Cached for 30 minutes unless ``fresh``."""
    with _lock:
        cached = _cache.get(id(ctx))
        if cached and not fresh and time.time() - cached[0] < CACHE_SECONDS:
            return cached[1]
    facts = gather(ctx)
    prompt = f"""Give me my briefing for today, written to be read aloud: about 120-170 words, warm
and crisp, in your JARVIS voice, no lists, headings or emoji. Open with "Good {_part_of_day(facts['time'])},
{facts['name']}." Cover, in this order: the weather; today's calendar events; important unread email (who and what, briefly); today's reminders; the most important open tasks;
then search the web and give the top 3 news headlines for today, focused on the UAE{
" and " + facts["city"] if facts.get("city") else ""} plus one big world story, one short sentence each.
Skip anything that's missing rather than mentioning it.

Today's facts:
{as_text(facts)}"""
    conv = f"briefing-{int(time.time() * 1000)}"
    try:
        brain = make_brain(conversation_id=conv, tools=[], web_search=True, remember_facts=False, effort="low")
        text = brain.chat(prompt).text.strip()
    except Exception:
        log.exception("Couldn't compose the briefing with the AI; using the plain version")
        text = fallback(facts)
    finally:
        ctx.db.delete_conversation(conv)  # briefings don't need to pile up in the database
    with _lock:
        _cache[id(ctx)] = (time.time(), text)
    return text


def due(ctx: Context, now: datetime | None = None) -> bool:
    """True when this morning's briefing should go out now (and hasn't yet)."""
    setting = ctx.settings.briefing_time
    if not setting or setting == "off":
        return False
    try:
        hour, minute = (int(x) for x in setting.split(":"))
    except ValueError:
        return False
    now = now or datetime.now(ctx.settings.tz)
    if (now.hour, now.minute) < (hour, minute) or now.hour >= 12:
        return False  # too early, or the morning has passed (e.g. the server was asleep)
    return ctx.db.get_kv("last_briefing") != now.date().isoformat()


def send_if_due(ctx: Context, make_brain: Callable[..., Any], now: datetime | None = None) -> bool:
    """Send the morning briefing if it's due. Returns True when one was sent."""
    now = now or datetime.now(ctx.settings.tz)
    if not due(ctx, now):
        return False
    ctx.db.set_kv("last_briefing", now.date().isoformat())  # claim it first: never send twice
    ctx.notifier.publish("briefing", compose(ctx, make_brain, fresh=True))
    return True
