"""Contacts, phone calls and texts."""

from __future__ import annotations

from jarvis.db import utcnow
from jarvis.phone import PhoneError, normalize_number
from jarvis.tools import Context, ToolError, tool


def find_contact(ctx: Context, who: str) -> tuple[str, str]:
    """Resolve a contact name (or a raw phone number) to (name, number)."""
    who = (who or "").strip()
    if who.startswith("+") or who.startswith("00"):
        try:
            return who, normalize_number(who)
        except PhoneError as exc:
            raise ToolError(str(exc)) from exc
    row = ctx.db.one("SELECT * FROM contacts WHERE name = ? COLLATE NOCASE", (who,))
    if not row:
        row = ctx.db.one("SELECT * FROM contacts WHERE name LIKE ? ORDER BY length(name)", (f"%{who}%",))
    if not row:
        raise ToolError(f"No contact called '{who}'. Ask the user for their number and save it with add_contact.")
    return row["name"], row["phone"]


@tool(
    "add_contact",
    "Save (or update) a contact so Jarvis can call or text them by name.",
    {
        "name": {"type": "string"},
        "phone": {"type": "string", "description": "International format with country code, e.g. +15551234567"},
        "relationship": {"type": "string", "description": "e.g. mom, boss, friend, dentist"},
    },
    ["name", "phone"],
)
def add_contact(ctx: Context, args: dict) -> str:
    try:
        phone = normalize_number(args["phone"])
    except PhoneError as exc:
        raise ToolError(str(exc)) from exc
    ctx.db.execute(
        "INSERT INTO contacts (name, phone, relationship, created_at) VALUES (?, ?, ?, ?) "
        "ON CONFLICT(name) DO UPDATE SET phone = excluded.phone, relationship = excluded.relationship",
        (args["name"].strip(), phone, args.get("relationship") or "", utcnow()),
    )
    return f"Saved contact {args['name']} ({phone})."


@tool("list_contacts", "List saved contacts.")
def list_contacts(ctx: Context, args: dict) -> str:
    rows = ctx.db.query("SELECT * FROM contacts ORDER BY name")
    if not rows:
        return "No contacts saved yet."
    return "\n".join(
        f"{r['name']}: {r['phone']}" + (f" ({r['relationship']})" if r["relationship"] else "") for r in rows
    )


@tool("delete_contact", "Delete a saved contact.", {"name": {"type": "string"}}, ["name"])
def delete_contact(ctx: Context, args: dict) -> str:
    if not ctx.db.execute("DELETE FROM contacts WHERE name = ? COLLATE NOCASE", (args["name"],)):
        raise ToolError(f"No contact called '{args['name']}'.")
    return f"Deleted contact {args['name']}."


def _conversation_note(ctx: Context, wanted: bool) -> str:
    if wanted and not ctx.phone.can_converse:
        return " (Two-way conversation needs PUBLIC_BASE_URL, so the message will just be read out.)"
    return ""


@tool(
    "call_me",
    "Phone the user (the owner) on their own phone. Set conversation=true to "
    "have a spoken back-and-forth with Jarvis on the call.",
    {
        "message": {"type": "string", "description": "What Jarvis says when the user picks up."},
        "conversation": {"type": "boolean"},
    },
    ["message"],
    needs_phone=True,
)
def call_me(ctx: Context, args: dict) -> str:
    wanted = bool(args.get("conversation"))
    try:
        call_id = ctx.phone.call_owner(args["message"], conversation=wanted and ctx.phone.can_converse)
    except PhoneError as exc:
        raise ToolError(str(exc)) from exc
    return f"Calling you now (call #{call_id}).{_conversation_note(ctx, wanted)}"


@tool(
    "text_me",
    "Send the user (the owner) a text message on their own phone.",
    {"message": {"type": "string"}},
    ["message"],
    needs_phone=True,
)
def text_me(ctx: Context, args: dict) -> str:
    try:
        ctx.phone.text_owner(args["message"])
    except PhoneError as exc:
        raise ToolError(str(exc)) from exc
    return "Text sent to you."


def _summarize_call(ctx: Context, args: dict) -> str:
    try:
        name, number = find_contact(ctx, args.get("who", ""))
    except ToolError:
        name, number = args.get("who", "?"), "unknown number"
    kind = "Call (two-way)" if args.get("conversation") else "Call"
    return f"{kind} {name} ({number}) and say: \"{args.get('message', '')}\""


@tool(
    "call_contact",
    "Phone someone else (a saved contact or a +number) on the user's behalf. "
    "Jarvis introduces itself as the user's assistant and delivers the message. "
    "With conversation=true Jarvis talks with them and reports back what they "
    "said. The user must approve every call; the app asks them automatically.",
    {
        "who": {"type": "string", "description": "Contact name, or a full +international number."},
        "message": {"type": "string", "description": "The message / purpose of the call."},
        "conversation": {"type": "boolean"},
    },
    ["who", "message"],
    needs_phone=True,
    needs_approval=True,
    summarize=_summarize_call,
)
def call_contact(ctx: Context, args: dict) -> str:
    name, number = find_contact(ctx, args["who"])
    wanted = bool(args.get("conversation"))
    intro = f"Hello, this is Jarvis, {ctx.settings.my_name}'s AI assistant, calling with a message. "
    try:
        call_id = ctx.phone.call(
            number, intro + args["message"], contact_name=name, conversation=wanted and ctx.phone.can_converse
        )
    except PhoneError as exc:
        raise ToolError(str(exc)) from exc
    return f"Calling {name} now (call #{call_id}).{_conversation_note(ctx, wanted)}"


def _summarize_text(ctx: Context, args: dict) -> str:
    try:
        name, number = find_contact(ctx, args.get("who", ""))
    except ToolError:
        name, number = args.get("who", "?"), "unknown number"
    return f"Text {name} ({number}): \"{args.get('message', '')}\""


@tool(
    "text_contact",
    "Send a text message to someone else (a saved contact or a +number). The "
    "user must approve; the app asks them automatically.",
    {"who": {"type": "string"}, "message": {"type": "string"}},
    ["who", "message"],
    needs_phone=True,
    needs_approval=True,
    summarize=_summarize_text,
)
def text_contact(ctx: Context, args: dict) -> str:
    name, number = find_contact(ctx, args["who"])
    try:
        ctx.phone.text(number, args["message"])
    except PhoneError as exc:
        raise ToolError(str(exc)) from exc
    return f"Text sent to {name}."
