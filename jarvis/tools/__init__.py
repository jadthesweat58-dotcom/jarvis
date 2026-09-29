"""Tool registry: every action Jarvis can take is a Tool.

Each tool module registers its functions with the ``@tool`` decorator. A tool
handler receives the shared ``Context`` plus the input Claude chose, and
returns a short string that is sent back to Claude as the tool result.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any, Callable

if TYPE_CHECKING:
    from jarvis.config import Settings
    from jarvis.db import Database
    from jarvis.notify import Notifier
    from jarvis.phone import Phone


class ToolError(Exception):
    """Raised by a tool for an expected failure; the message goes back to Claude."""


@dataclass
class Context:
    db: "Database"
    settings: "Settings"
    notifier: "Notifier"
    phone: "Phone"
    # vision(image_bytes, mime_type, question) -> what the AI sees; set by the brain.
    vision: Callable[[bytes, str, str], str] | None = None


@dataclass
class Tool:
    name: str
    description: str
    parameters: dict[str, Any]
    required: list[str]
    handler: Callable[[Context, dict], str]
    # True, or a function deciding per call, when the user must approve first.
    needs_approval: bool | Callable[[Context, dict], bool] = False
    # One-line description of the action shown to the user when approval is needed.
    summarize: Callable[[Context, dict], str] | None = None
    # Optional: settle details before asking for approval, so the user approves
    # exactly what will run (e.g. turn a contact name into the phone number).
    prepare: Callable[[Context, dict], dict] | None = None
    local_only: bool = False
    needs_phone: bool = False
    needs_gemini: bool = False   # uses Google services beyond chat (pictures)

    def definition(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "description": self.description,
            "input_schema": {
                "type": "object",
                "properties": self.parameters,
                "required": self.required,
            },
        }

    def requires_approval(self, ctx: Context, args: dict) -> bool:
        if callable(self.needs_approval):
            return self.needs_approval(ctx, args)
        return bool(self.needs_approval)

    def describe(self, ctx: Context, args: dict) -> str:
        if self.summarize:
            return self.summarize(ctx, args)
        return f"{self.name}({args})"


REGISTRY: dict[str, Tool] = {}


def tool(
    name: str,
    description: str,
    parameters: dict[str, Any] | None = None,
    required: list[str] | None = None,
    **options: Any,
) -> Callable[[Callable[[Context, dict], str]], Callable[[Context, dict], str]]:
    def register(fn: Callable[[Context, dict], str]) -> Callable[[Context, dict], str]:
        REGISTRY[name] = Tool(
            name=name,
            description=description,
            parameters=parameters or {},
            required=required or [],
            handler=fn,
            **options,
        )
        return fn

    return register


def available_tools(settings: "Settings") -> list[Tool]:
    """Tools usable in the current setup (local-only and phone tools filtered out)."""
    load_all()
    tools = []
    for t in REGISTRY.values():
        if t.local_only and not settings.is_local:
            continue
        if t.needs_phone and not settings.twilio_enabled:
            continue
        if t.needs_gemini and not settings.gemini_api_key:
            continue
        tools.append(t)
    return tools


def load_all() -> None:
    # Importing the modules runs their @tool decorators.
    from jarvis.tools import (  # noqa: F401
        automations, calls, computer, extras, library, memory, notes, pictures, reminders, web,
    )
