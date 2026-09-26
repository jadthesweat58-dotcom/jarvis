"""Notes and to-do list."""

from __future__ import annotations

from jarvis.db import utcnow
from jarvis.tools import Context, ToolError, tool


@tool(
    "add_note",
    "Save a note (ideas, lists, info the user wants to keep).",
    {"title": {"type": "string"}, "body": {"type": "string"}},
    ["title"],
)
def add_note(ctx: Context, args: dict) -> str:
    note_id = ctx.db.execute(
        "INSERT INTO notes (title, body, created_at) VALUES (?, ?, ?)",
        (args["title"].strip(), (args.get("body") or "").strip(), utcnow()),
    )
    return f"Saved note #{note_id}."


@tool(
    "search_notes",
    "Find notes by keyword. Leave query empty to list the most recent notes.",
    {"query": {"type": "string"}},
)
def search_notes(ctx: Context, args: dict) -> str:
    query = (args.get("query") or "").strip()
    if query:
        rows = ctx.db.query(
            "SELECT * FROM notes WHERE title LIKE ? OR body LIKE ? ORDER BY id DESC LIMIT 20",
            (f"%{query}%", f"%{query}%"),
        )
    else:
        rows = ctx.db.query("SELECT * FROM notes ORDER BY id DESC LIMIT 20")
    if not rows:
        return "No notes found."
    return "\n\n".join(f"#{r['id']} {r['title']} ({r['created_at'][:10]})\n{r['body']}" for r in rows)


@tool("delete_note", "Delete a note by id.", {"id": {"type": "integer"}}, ["id"])
def delete_note(ctx: Context, args: dict) -> str:
    if not ctx.db.execute("DELETE FROM notes WHERE id = ?", (args["id"],)):
        raise ToolError(f"No note #{args['id']}.")
    return f"Deleted note #{args['id']}."


@tool(
    "add_todo",
    "Add a task to the user's to-do list.",
    {
        "task": {"type": "string"},
        "due": {"type": "string", "description": "Optional due date, e.g. 2026-10-01."},
    },
    ["task"],
)
def add_todo(ctx: Context, args: dict) -> str:
    todo_id = ctx.db.execute(
        "INSERT INTO todos (task, due, created_at) VALUES (?, ?, ?)",
        (args["task"].strip(), args.get("due") or None, utcnow()),
    )
    return f"Added to-do #{todo_id}."


@tool(
    "list_todos",
    "Show the to-do list.",
    {"include_done": {"type": "boolean", "description": "Also show finished tasks."}},
)
def list_todos(ctx: Context, args: dict) -> str:
    sql = "SELECT * FROM todos"
    if not args.get("include_done"):
        sql += " WHERE done = 0"
    rows = ctx.db.query(sql + " ORDER BY done, COALESCE(due, '9999'), id")
    if not rows:
        return "The to-do list is empty."
    lines = []
    for r in rows:
        mark = "x" if r["done"] else " "
        due = f" (due {r['due']})" if r["due"] else ""
        lines.append(f"[{mark}] #{r['id']} {r['task']}{due}")
    return "\n".join(lines)


@tool("complete_todo", "Mark a to-do as done.", {"id": {"type": "integer"}}, ["id"])
def complete_todo(ctx: Context, args: dict) -> str:
    if not ctx.db.execute("UPDATE todos SET done = 1 WHERE id = ?", (args["id"],)):
        raise ToolError(f"No to-do #{args['id']}.")
    return f"Marked to-do #{args['id']} as done."
