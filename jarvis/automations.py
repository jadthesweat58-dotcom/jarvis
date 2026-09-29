"""Routines and watchers: work Jarvis does on its own, on a schedule.

- A **routine** is a task in plain words run on a schedule ("every Friday at 6pm,
  find fun things to do in Dubai this weekend"). Jarvis does it with a fresh,
  restricted brain (it can search the web and use safe tools, but can never
  call, text, run commands or do anything else that needs your approval) and
  sends you the result.
- A **watcher** checks a web page every few hours and tells you when a
  condition is met ("price below 500 AED") or when the page meaningfully changes.

Both are started by the server's once-a-minute tick; results go out as
notifier events (dashboard, phone notification, Telegram).
"""

from __future__ import annotations

import difflib
import json
import logging
import re
import time
from datetime import datetime, timedelta, timezone
from typing import Any, Callable

from jarvis.tools import Context, Tool, ToolError, available_tools
from jarvis.tools.reminders import next_due

log = logging.getLogger("jarvis.automations")

MAX_ROUTINES = 20
MAX_WATCHERS = 20
MAX_FAILS = 3
SNAPSHOT_CHARS = 20_000
# Tools a routine may not use even though they need no approval: no routines that
# make routines, no surprise picture bills, no phone calls.
ROUTINE_BLOCKED = {"create_routine", "delete_routine", "run_routine_now", "watch_page", "stop_watcher",
                   "generate_image", "forget_document", "delete_note", "delete_contact", "cancel_reminder"}

WATCH_SYSTEM = """You check web pages for JARVIS, a personal assistant. Read the page text you are
given and answer ONLY with a single JSON object, no other text."""


def iso(dt: datetime) -> str:
    return dt.astimezone(timezone.utc).isoformat(timespec="seconds")


def now_utc() -> datetime:
    return datetime.now(timezone.utc)


def safe_tools(settings: Any) -> list[Tool]:
    """Tools a routine may use on its own: nothing that needs approval, touches the
    computer, uses the phone, or costs extra."""
    return [t for t in available_tools(settings)
            if t.needs_approval is False and not t.local_only and not t.needs_phone
            and t.name not in ROUTINE_BLOCKED]


def _throwaway(make_brain: Callable[..., Any], prefix: str, **kw: Any) -> tuple[Any, str]:
    conv = f"{prefix}-{int(time.time() * 1000)}"
    return make_brain(conversation_id=conv, **kw), conv


# ------------------------------------------------------------------ routines
def run_due_routines(ctx: Context, make_brain: Callable[..., Any], now: datetime | None = None) -> int:
    now = now or now_utc()
    due = ctx.db.query("SELECT * FROM routines WHERE enabled = 1 AND next_run <= ? ORDER BY next_run", (iso(now),))
    ran = 0
    for r in due:
        following = next_due(r["next_run"], r["rule"], ctx.settings.tz, now)
        # Claim it by moving it on, so it runs once even if two ticks overlap.
        if not ctx.db.execute("UPDATE routines SET next_run = ?, last_run = ? WHERE id = ? AND next_run = ? AND enabled = 1",
                              (following, iso(now), r["id"], r["next_run"])):
            continue
        run_routine(ctx, make_brain, r)
        ran += 1
    return ran


def run_routine(ctx: Context, make_brain: Callable[..., Any], routine: dict) -> str:
    local = datetime.now(ctx.settings.tz).strftime("%A %d %B, %H:%M")
    prompt = (f"(This is your scheduled routine \"{routine['title']}\", running by itself at {local}. "
              f"{ctx.settings.my_name} isn't in the chat right now: do the task with your tools, then reply "
              "with exactly what they should receive: short, useful, ready to read on a phone. Don't ask "
              f"questions back.)\n\nThe task: {routine['prompt']}")
    brain, conv = _throwaway(make_brain, f"routine-{routine['id']}", tools=safe_tools(ctx.settings),
                             web_search=True, effort="low")
    try:
        result = brain.chat(prompt).text.strip()
    except Exception as exc:
        log.exception("Routine #%s failed", routine["id"])
        result = f"I couldn't finish this one: {type(exc).__name__}."
    finally:
        ctx.db.delete_conversation(conv)
    ctx.db.execute("UPDATE routines SET last_result = ? WHERE id = ?", (result[:4000], routine["id"]))
    ctx.notifier.publish("routine", f"{routine['title']}: {result}", id=routine["id"])
    return result


# ------------------------------------------------------------------ watchers
def _judge(make_brain: Callable[..., Any], ctx: Context, prompt: str) -> dict:
    brain, conv = _throwaway(make_brain, "watch", tools=[], web_search=False, remember_facts=False,
                             effort="low", system_prompt=WATCH_SYSTEM)
    try:
        answer = brain.chat(prompt).text
    finally:
        ctx.db.delete_conversation(conv)
    match = re.search(r"\{.*\}", answer, re.S)
    if not match:
        raise ValueError("no JSON in the answer")
    return json.loads(match.group(0))


def _diff(old: str, new: str, limit: int = 4000) -> str:
    lines = difflib.unified_diff(old.splitlines(), new.splitlines(), lineterm="", n=0)
    body = [l for l in lines if l[:1] in "+-" and not l.startswith(("+++", "---")) and l[1:].strip()]
    return "\n".join(body)[:limit]


def run_due_watchers(ctx: Context, make_brain: Callable[..., Any], now: datetime | None = None,
                     fetch: Callable[[str], tuple[str, str, str]] | None = None) -> int:
    now = now or now_utc()
    due = ctx.db.query("SELECT * FROM watchers WHERE status = 'active' AND next_check <= ? ORDER BY next_check",
                       (iso(now),))
    checked = 0
    for w in due:
        following = iso(now + timedelta(hours=max(1, int(w["every_hours"] or 6))))
        if not ctx.db.execute("UPDATE watchers SET next_check = ? WHERE id = ? AND next_check = ? AND status = 'active'",
                              (following, w["id"], w["next_check"])):
            continue
        check_watcher(ctx, make_brain, w, fetch=fetch)
        checked += 1
    return checked


def check_watcher(ctx: Context, make_brain: Callable[..., Any], w: dict,
                  fetch: Callable[[str], tuple[str, str, str]] | None = None) -> str:
    if fetch is None:
        from jarvis.tools.extras import fetch_page as fetch
    stamp = iso(now_utc())
    try:
        _, title, text = fetch(w["url"])
    except Exception as exc:
        fails = int(w["fails"] or 0) + 1
        reason = str(exc) if isinstance(exc, ToolError) else type(exc).__name__
        if fails >= MAX_FAILS:
            ctx.db.execute("UPDATE watchers SET fails = ?, status = 'paused', last_checked = ?, last_note = ? WHERE id = ?",
                           (fails, stamp, f"Paused: {reason}", w["id"]))
            ctx.notifier.publish("watch", f"I stopped watching {w['url']} after {fails} failed tries ({reason}). "
                                          "Some sites block automatic checks.", id=w["id"])
        else:
            ctx.db.execute("UPDATE watchers SET fails = ?, last_checked = ?, last_note = ? WHERE id = ?",
                           (fails, stamp, f"Couldn't open it: {reason}", w["id"]))
        return "failed"
    text = text.strip()[:SNAPSHOT_CHARS]
    label = title.strip() or w["url"]
    note, alert, status = "", "", "active"
    try:
        if w["condition"]:
            verdict = _judge(make_brain, ctx, (
                f"The user asked to be told when this is true: \"{w['condition']}\".\n"
                f"Page: {label} ({w['url']})\n\nPAGE TEXT:\n{text[:12000]}\n\n"
                'Reply as JSON: {"met": true or false, "detail": "one short sentence with the relevant '
                'figure or fact as it is now"}'))
            note = str(verdict.get("detail", ""))[:500]
            if verdict.get("met") is True:
                alert, status = f"✅ {w['condition']}: {note} ({w['url']})", "done"
        elif not w["snapshot"]:
            note = "First look saved; I'll tell you when it changes."
        elif text != w["snapshot"]:
            changes = _diff(w["snapshot"], text)
            if changes:
                verdict = _judge(make_brain, ctx, (
                    f"This page changed since the last check: {label} ({w['url']}).\nCHANGED LINES (- old, + new):\n"
                    f"{changes}\n\nIgnore trivial changes (dates, times, view counts, ads, cookie banners, "
                    'reordering). Reply as JSON: {"meaningful": true or false, "summary": "one or two short '
                    'sentences saying what changed"}'))
                note = str(verdict.get("summary", ""))[:500]
                if verdict.get("meaningful") is True:
                    alert = f"🔎 {label} changed: {note} ({w['url']})"
    except Exception as exc:
        log.warning("Watcher #%s couldn't judge the page: %s", w["id"], type(exc).__name__)
        note = "Checked the page but couldn't judge it this time."
    ctx.db.execute("UPDATE watchers SET snapshot = ?, fails = 0, last_checked = ?, last_note = ?, status = ? WHERE id = ?",
                   (text, stamp, note, status, w["id"]))
    if alert:
        ctx.notifier.publish("watch", alert, id=w["id"])
    return alert or note
