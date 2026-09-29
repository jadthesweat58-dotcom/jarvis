"""Routines (scheduled AI tasks) and watchers (web page alerts), set up by talking."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

from jarvis.db import utcnow
from jarvis.tools import Context, ToolError, tool
from jarvis.tools.reminders import REPEATS, describe_repeat, parse_when, repeat_rule, to_local


# ------------------------------------------------------------------ routines
@tool(
    "create_routine",
    "Schedule a task Jarvis does by itself and sends the user the result, e.g. 'every Friday at 6pm "
    "find fun events in Dubai this weekend' or 'every weekday at 7:45 give me the top tech news'. "
    "Routines can search the web and read pages but can't call, text or run commands. For a plain "
    "alert with fixed text, use set_reminder instead.",
    {
        "title": {"type": "string", "description": "Short name, e.g. 'Weekend plans'."},
        "prompt": {"type": "string", "description": "The task in plain words, as the user would ask it."},
        "at": {"type": "string", "description": "First run, local time ISO: 2026-10-02T18:00"},
        "in_minutes": {"type": "number", "description": "First run in this many minutes (instead of 'at')."},
        "repeat": {"type": "string", "enum": REPEATS, "description": "How often. Default daily."},
    },
    ["title", "prompt"],
)
def create_routine(ctx: Context, args: dict) -> str:
    from jarvis.automations import MAX_ROUTINES

    count = ctx.db.one("SELECT COUNT(*) AS n FROM routines")["n"]
    if int(count or 0) >= MAX_ROUTINES:
        raise ToolError(f"There are already {MAX_ROUTINES} routines; delete one first.")
    when = parse_when(ctx, args)
    rule = repeat_rule(args.get("repeat") or "daily", when, ctx.settings.tz)
    rid = ctx.db.execute(
        "INSERT INTO routines (title, prompt, rule, next_run, created_at) VALUES (?, ?, ?, ?, ?)",
        (str(args["title"]).strip()[:120], str(args["prompt"]).strip()[:2000], rule,
         when.isoformat(timespec="seconds"), utcnow()))
    return (f"Routine #{rid} \"{args['title']}\" set: {describe_repeat(rule)}, first run "
            f"{to_local(ctx, when.isoformat())}. Results arrive as a notification.")


@tool("list_routines", "List the user's routines (scheduled AI tasks) with their last results.")
def list_routines(ctx: Context, args: dict) -> str:
    rows = ctx.db.query("SELECT * FROM routines ORDER BY id")
    if not rows:
        return "No routines yet."
    return "\n".join(
        f"#{r['id']} {r['title']} ({describe_repeat(r['rule'])}{'' if r['enabled'] else ', paused'}; "
        f"next {to_local(ctx, r['next_run'])}): {r['prompt']}"
        + (f"\n   Last result: {r['last_result'][:300]}" if r["last_result"] else "")
        for r in rows)


@tool("delete_routine", "Delete a routine by id.", {"id": {"type": "integer"}}, ["id"])
def delete_routine(ctx: Context, args: dict) -> str:
    if not ctx.db.execute("DELETE FROM routines WHERE id = ?", (args["id"],)):
        raise ToolError(f"No routine #{args['id']}.")
    return f"Deleted routine #{args['id']}."


@tool("run_routine_now", "Run a routine right away (the result arrives within a minute or two).",
      {"id": {"type": "integer"}}, ["id"])
def run_routine_now(ctx: Context, args: dict) -> str:
    if not queue_now(ctx, "routine", int(args["id"])):
        raise ToolError(f"No routine #{args['id']}.")
    return f"Routine #{args['id']} will run within a minute; the result will arrive as a notification."


def queue_now(ctx: Context, kind: str, item_id: int) -> bool:
    """Make a routine or watcher due now (the tick picks it up within a minute).
    Setting it a moment in the past keeps a routine's clock time for later runs."""
    soon = (datetime.now(timezone.utc) - timedelta(seconds=1)).isoformat(timespec="seconds")
    if kind == "routine":
        row = ctx.db.one("SELECT next_run FROM routines WHERE id = ?", (item_id,))
        if not row:
            return False
        # Keep the original time of day: run now, then carry on from the next scheduled slot.
        return bool(ctx.db.execute("UPDATE routines SET next_run = ?, enabled = 1 WHERE id = ?", (soon, item_id)))
    return bool(ctx.db.execute("UPDATE watchers SET next_check = ?, status = 'active', fails = 0 WHERE id = ?",
                               (soon, item_id)))


# ------------------------------------------------------------------ watchers
@tool(
    "watch_page",
    "Keep an eye on a web page and alert the user: either when a condition becomes true ('price below "
    "500 AED', 'tickets are on sale', 'the store says in stock') or, with no condition, when the page "
    "changes in a meaningful way. Checks every few hours. Some shops block automatic checks.",
    {
        "url": {"type": "string"},
        "condition": {"type": "string", "description": "What to wait for, in plain words. Leave empty for any meaningful change."},
        "every_hours": {"type": "integer", "description": "How often to check (1-168). Default 6."},
    },
    ["url"],
)
def watch_page(ctx: Context, args: dict) -> str:
    from jarvis import safeurl
    from jarvis.automations import MAX_WATCHERS

    url = str(args.get("url", "")).strip()
    if url and "://" not in url:
        url = "https://" + url
    try:
        safeurl.check_url(url)
    except safeurl.UnsafeURL as exc:
        raise ToolError(str(exc)) from exc
    active = ctx.db.one("SELECT COUNT(*) AS n FROM watchers WHERE status = 'active'")["n"]
    if int(active or 0) >= MAX_WATCHERS:
        raise ToolError(f"Already watching {MAX_WATCHERS} pages; stop one first.")
    hours = min(max(int(args.get("every_hours") or 6), 1), 168)
    condition = str(args.get("condition") or "").strip()[:300]
    wid = ctx.db.execute(
        "INSERT INTO watchers (url, condition, every_hours, next_check, created_at) VALUES (?, ?, ?, ?, ?)",
        (url, condition, hours, utcnow(), utcnow()))
    what = f"until {condition}" if condition else "for meaningful changes"
    return f"Watcher #{wid} set: checking {url} every {hours}h {what}. The first check happens within a minute."


@tool("list_watchers", "List the pages Jarvis is watching and what it last saw.")
def list_watchers(ctx: Context, args: dict) -> str:
    rows = ctx.db.query("SELECT * FROM watchers ORDER BY id")
    if not rows:
        return "Not watching any pages."
    return "\n".join(
        f"#{w['id']} [{w['status']}] {w['url']} — {w['condition'] or 'any meaningful change'}, every {w['every_hours']}h"
        + (f"\n   Last check: {w['last_note']}" if w["last_note"] else "")
        for w in rows)


@tool("stop_watcher", "Stop watching a page (delete the watcher) by id.", {"id": {"type": "integer"}}, ["id"])
def stop_watcher(ctx: Context, args: dict) -> str:
    if not ctx.db.execute("DELETE FROM watchers WHERE id = ?", (args["id"],)):
        raise ToolError(f"No watcher #{args['id']}.")
    return f"Stopped watcher #{args['id']}."
