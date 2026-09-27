"""Long-term memory: facts about the user that Jarvis should never forget."""

from __future__ import annotations

from jarvis.db import utcnow
from jarvis.tools import Context, ToolError, tool


@tool(
    "remember_fact",
    "Save a lasting fact about the user or their world (preferences, people, "
    "birthdays, routines, goals). Use whenever the user shares something worth "
    "remembering, even if they don't explicitly ask you to remember it.",
    {
        "fact": {"type": "string", "description": "The fact, written as a full sentence."},
        "category": {
            "type": "string",
            "description": "e.g. personal, people, preferences, work, health, other",
        },
    },
    ["fact"],
)
def remember_fact(ctx: Context, args: dict) -> str:
    fact = args["fact"].strip()
    if not fact:
        raise ToolError("The fact is empty.")
    fact_id = ctx.db.execute(
        "INSERT INTO facts (fact, category, created_at) VALUES (?, ?, ?)",
        (fact, args.get("category") or "general", utcnow()),
    )
    return f"Saved fact #{fact_id}."


@tool(
    "recall_facts",
    "Search the facts saved about the user. Leave query empty to list everything.",
    {"query": {"type": "string", "description": "Word or phrase to search for."}},
)
def recall_facts(ctx: Context, args: dict) -> str:
    query = (args.get("query") or "").strip()
    if query:
        rows = ctx.db.query(
            "SELECT * FROM facts WHERE lower(fact) LIKE lower(?) OR lower(category) LIKE lower(?) ORDER BY id",
            (f"%{query}%", f"%{query}%"),
        )
    else:
        rows = ctx.db.query("SELECT * FROM facts ORDER BY id")
    if not rows:
        return "No matching facts saved."
    return "\n".join(f"#{r['id']} [{r['category']}] {r['fact']}" for r in rows)


@tool(
    "forget_fact",
    "Delete a saved fact by its id (use recall_facts to find the id).",
    {"id": {"type": "integer"}},
    ["id"],
)
def forget_fact(ctx: Context, args: dict) -> str:
    if not ctx.db.execute("DELETE FROM facts WHERE id = ?", (args["id"],)):
        raise ToolError(f"No fact #{args['id']}.")
    return f"Forgot fact #{args['id']}."


def facts_for_prompt(ctx: Context, limit: int = 200) -> str:
    rows = ctx.db.query("SELECT fact FROM facts ORDER BY id DESC LIMIT ?", (limit,))
    return "\n".join(f"- {r['fact']}" for r in reversed(rows))
