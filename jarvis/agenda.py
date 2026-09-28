"""Your calendar, read from its private iCal link (CALENDAR_ICS_URL).

Google Calendar, Outlook and Apple Calendar can all share a calendar as a
secret .ics address, so Jarvis can read it without any sign-in or API key.
Several links can be given, separated by commas. Read-only.
"""

from __future__ import annotations

import logging
import threading
import time
from datetime import date, datetime, timedelta
from typing import Any

import httpx

from jarvis.tools import Context

log = logging.getLogger("jarvis.agenda")

CACHE_SECONDS = 10 * 60
_cache: dict[str, tuple[float, bytes]] = {}
_lock = threading.Lock()


def _download(url: str, client: Any = None) -> bytes:
    url = url.strip()
    if url.startswith("webcal://"):
        url = "https://" + url[len("webcal://"):]
    with _lock:
        cached = _cache.get(url)
        if cached and time.time() - cached[0] < CACHE_SECONDS:
            return cached[1]
    http = client or httpx
    resp = http.get(url, timeout=15, follow_redirects=True)
    resp.raise_for_status()
    with _lock:
        _cache[url] = (time.time(), resp.content)
    return resp.content


def events_between(ctx: Context, start: datetime, end: datetime, client: Any = None) -> list[dict[str, Any]]:
    """Events overlapping [start, end), soonest first, from every configured calendar.
    A calendar that can't be read is skipped (and logged)."""
    import icalendar
    import recurring_ical_events
    import x_wr_timezone

    tz = ctx.settings.tz
    found: list[dict[str, Any]] = []
    for url in ctx.settings.calendar_urls:
        try:
            cal = x_wr_timezone.to_standard(icalendar.Calendar.from_ical(_download(url, client)))
            occurrences = recurring_ical_events.of(cal).between(start, end)
        except Exception:
            log.warning("Couldn't read a calendar", exc_info=True)
            continue
        for ev in occurrences:
            if str(ev.get("STATUS", "")).upper() == "CANCELLED":
                continue
            begin = ev.get("DTSTART").dt
            finish = ev.get("DTEND").dt if ev.get("DTEND") else None
            all_day = not isinstance(begin, datetime)
            if all_day:
                begin_local = datetime.combine(begin, datetime.min.time(), tz)
                end_local = datetime.combine(finish, datetime.min.time(), tz) if isinstance(finish, date) \
                    else begin_local + timedelta(days=1)
            else:
                begin_local = (begin if begin.tzinfo else begin.replace(tzinfo=tz)).astimezone(tz)
                end_local = ((finish if finish.tzinfo else finish.replace(tzinfo=tz)).astimezone(tz)
                             if isinstance(finish, datetime) else begin_local)
            found.append({
                "title": str(ev.get("SUMMARY", "") or "(busy)").strip(),
                "location": str(ev.get("LOCATION", "") or "").strip(),
                "start": begin_local.isoformat(),
                "end": end_local.isoformat(),
                "all_day": all_day,
            })
    found.sort(key=lambda e: (e["start"], not e["all_day"]))
    return found


def today(ctx: Context, client: Any = None) -> list[dict[str, Any]]:
    if not ctx.settings.calendar_urls:
        return []
    midnight = datetime.now(ctx.settings.tz).replace(hour=0, minute=0, second=0, microsecond=0)
    return events_between(ctx, midnight, midnight + timedelta(days=1), client)


def upcoming(ctx: Context, days: int = 1, client: Any = None) -> list[dict[str, Any]]:
    midnight = datetime.now(ctx.settings.tz).replace(hour=0, minute=0, second=0, microsecond=0)
    return events_between(ctx, midnight, midnight + timedelta(days=days), client)


def describe(event: dict[str, Any]) -> str:
    start = datetime.fromisoformat(event["start"])
    when = f"{start:%a %d %b}, all day" if event["all_day"] else \
        f"{start:%a %d %b %H:%M}–{datetime.fromisoformat(event['end']):%H:%M}"
    return f"{when}: {event['title']}" + (f" ({event['location']})" if event["location"] else "")
