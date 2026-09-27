"""Jarvis's brain: an AI conversation loop that can use tools.

``Brain.chat(text)`` sends the user's message to the AI model, runs whatever
tools it asks for, feeds the results back, and repeats until it answers.
``Brain`` talks to Claude; ``jarvis.gemini_brain.GeminiBrain`` talks to Gemini.
Use ``create_brain`` to get the one chosen by JARVIS_PROVIDER.

Conversation history is only ever appended to (never edited), and it is saved
to the database so Jarvis keeps its train of thought across restarts.
"""

from __future__ import annotations

import json
import logging
import threading
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Callable

import anthropic

from jarvis.db import utcnow
from jarvis.tools import Context, Tool, ToolError, available_tools
from jarvis.tools.memory import facts_for_prompt

log = logging.getLogger("jarvis.brain")

MAX_TOOL_ROUNDS = 15
MAX_HISTORY_MESSAGES = 120
# Models with the newest web search tool and server-side refusal fallbacks.
MODERN_WEB_SEARCH = ("claude-opus-5", "claude-fable-5", "claude-sonnet-5", "claude-opus-4-8",
                     "claude-opus-4-7", "claude-opus-4-6", "claude-sonnet-4-6")
FALLBACK_MODELS = ("claude-opus-5", "claude-fable-5-1")
# Models that take adaptive thinking and an effort level (older ones, e.g. Haiku 4.5, don't).
ADAPTIVE_MODELS = MODERN_WEB_SEARCH

# approver(tool, args, summary) -> True to run the tool, False to decline.
Approver = Callable[[Tool, dict, str], bool]


@dataclass
class Reply:
    text: str
    actions: list[dict] = field(default_factory=list)  # tool calls waiting for approval


def default_system_prompt(ctx: Context, tools: list[Tool], voice: bool = False) -> str:
    s = ctx.settings
    abilities = ["remember facts about the user", "keep notes and a to-do list",
                 "search the web", "check the weather", "set reminders and timers"]
    names = {t.name for t in tools}
    if "call_me" in names:
        abilities.append("phone and text the user, and call or text their contacts")
    if "run_command" in names:
        abilities.append("control the user's computer (open apps and websites, run commands, read files)")
    prompt = f"""You are JARVIS, the personal AI assistant of {s.my_name}. Address them as {s.my_name}.

Personality: calm, capable, quietly witty, with the polished manner of a British butler
(think Tony Stark's JARVIS). Be warm but never gushing.

You can: {"; ".join(abilities)}. Use your tools whenever they help; don't describe what you
would do, just do it. Never claim you did something unless a tool confirmed it.

Style: your replies are often read aloud, so keep them short and conversational (usually
1-3 sentences) unless {s.my_name} asks for detail. Avoid markdown, tables, emoji and long
URLs unless asked.

Memory: when {s.my_name} tells you something lasting about themselves, their people,
preferences or plans, save it with remember_fact without being asked. Check recall_facts
when a question might depend on something they told you before.

Time: each message from {s.my_name} starts with the current local date and time in
brackets. Their timezone is {s.timezone}. Use it to work out reminder times.

Approvals: calling or texting other people, running commands and writing files need
{s.my_name}'s approval. Just call the tool; the app asks them to approve. Never try to
get around a declined action."""
    if s.home_city:
        prompt += f"\n\n{s.my_name}'s home city is {s.home_city}."
    if voice:
        prompt += ("\n\nYou are speaking on a phone call. Keep every reply to one or two short "
                   "spoken sentences with no formatting at all. When the call is finished (they "
                   "say goodbye or need nothing else), say goodbye and end your reply with [HANGUP].")
    return prompt


def to_dict(block: Any) -> dict:
    return block if isinstance(block, dict) else block.model_dump(mode="json", exclude_none=True, by_alias=True)


class Brain:
    def __init__(
        self,
        ctx: Context,
        *,
        client: Any = None,
        conversation_id: str = "main",
        tools: list[Tool] | None = None,
        system_prompt: str | None = None,
        approver: Approver | None = None,
        effort: str | None = None,
        web_search: bool = True,
        remember_facts: bool = True,
        voice: bool = False,
    ):
        self.ctx = ctx
        self.settings = ctx.settings
        self.client = client
        self.conversation_id = conversation_id
        self.tools = available_tools(ctx.settings) if tools is None else tools
        self.tool_map = {t.name: t for t in self.tools}
        self.system_prompt = system_prompt or default_system_prompt(ctx, self.tools, voice=voice)
        self.approver = approver
        self.effort = effort or self.settings.effort
        self.web_search = web_search
        self.remember_facts = remember_facts
        self._lock = threading.Lock()
        self.messages: list[dict] = ctx.db.load_conversation(conversation_id)

    # --- public API -------------------------------------------------------------
    def chat(self, text: str) -> Reply:
        with self._lock:
            return self._chat(text)

    def reset(self) -> None:
        with self._lock:
            self.messages = []
            self.ctx.db.delete_conversation(self.conversation_id)

    # --- internals --------------------------------------------------------------
    def _client(self):
        if self.client is None:
            if not self.settings.anthropic_api_key:
                raise RuntimeError("ANTHROPIC_API_KEY is not set. Add it to your .env file (or your cloud host's environment settings).")
            self.client = anthropic.Anthropic(api_key=self.settings.anthropic_api_key)
        return self.client

    def _tool_definitions(self) -> list[dict]:
        defs: list[dict] = [t.definition() for t in self.tools]
        if self.web_search:
            modern = self.settings.model.startswith(MODERN_WEB_SEARCH)
            search: dict[str, Any] = {
                "type": "web_search_20260209" if modern else "web_search_20250305",
                "name": "web_search",
                "max_uses": 5,
            }
            location = {"type": "approximate", "timezone": self.settings.timezone}
            if self.settings.home_city:
                location["city"] = self.settings.home_city.split(",")[0].strip()
            search["user_location"] = location
            defs.append(search)
        return defs

    def _user_texts(self, text: str) -> list[str]:
        """The pieces of a new user turn: remembered facts (new conversations only)
        and the message itself, stamped with the local time."""
        now = datetime.now(self.settings.tz).strftime("%A %d %B %Y, %H:%M")
        texts: list[str] = []
        if not self.messages and self.remember_facts:
            # New conversation: hand the model everything it knows about the user.
            facts = facts_for_prompt(self.ctx)
            if facts:
                texts.append(f"<things_you_remember_about_me>\n{facts}\n</things_you_remember_about_me>")
        texts.append(f"[{now}] {text}")
        return texts

    def _user_turn(self, text: str) -> dict:
        return {"role": "user", "content": [{"type": "text", "text": t} for t in self._user_texts(text)]}

    def _request(self) -> Any:
        params: dict[str, Any] = {
            "model": self.settings.model,
            "max_tokens": 16000,
            "system": self.system_prompt,
            "messages": self.messages,
            "tools": self._tool_definitions(),
        }
        if self.settings.model.startswith(ADAPTIVE_MODELS):
            params["thinking"] = {"type": "adaptive"}
            params["output_config"] = {"effort": self.effort}
        if self.settings.model.startswith(FALLBACK_MODELS):
            # If the model declines, let the API retry on its recommended fallback model.
            params["betas"] = ["server-side-fallback-2026-07-01"]
            params["fallbacks"] = "default"
        return self._client().beta.messages.create(**params)

    def _chat(self, text: str) -> Reply:
        if len(self.messages) > MAX_HISTORY_MESSAGES:
            # Start a fresh conversation rather than editing history; saved facts carry over.
            self.messages = []
        checkpoint = len(self.messages)
        self.messages.append(self._user_turn(text))
        actions: list[dict] = []
        try:
            for _ in range(MAX_TOOL_ROUNDS):
                response = self._request()
                if response.stop_reason == "refusal":
                    del self.messages[checkpoint:]
                    return Reply("I'm afraid I can't help with that one.", actions)
                tool_uses = [b for b in response.content if b.type == "tool_use"]
                finished = response.stop_reason not in ("tool_use", "pause_turn") or (
                    response.stop_reason == "tool_use" and not tool_uses)
                content = response.content
                if finished:
                    # A reply cut off mid tool call (e.g. max_tokens) must not leave an
                    # unanswered tool_use in the history, or every later request fails.
                    content = [b for b in content if b.type != "tool_use"]
                self.messages.append({"role": "assistant", "content": [to_dict(b) for b in content]
                                      or [{"type": "text", "text": "(no reply)"}]})
                if response.stop_reason == "pause_turn":
                    continue  # server-side web search paused; re-send to let it resume
                if finished:
                    self._save()
                    return Reply(self._text_of(content), actions)
                results = [self._run_tool(b, actions) for b in tool_uses]
                self.messages.append({"role": "user", "content": results})
            self._save()
            return Reply("I've been going round in circles on that one; could you rephrase?", actions)
        except Exception:
            # Roll back to where we started so a failed turn can't corrupt the history.
            del self.messages[checkpoint:]
            raise

    @staticmethod
    def _text_of(content: list[Any]) -> str:
        return "\n".join(b.text for b in content if b.type == "text").strip() or "Done."

    def _run_tool(self, block: Any, actions: list[dict]) -> dict:
        output, is_error = self._execute_tool(block.name, dict(block.input or {}), actions)
        result: dict[str, Any] = {"type": "tool_result", "tool_use_id": block.id, "content": output}
        if is_error:
            result["is_error"] = True
        return result

    def _execute_tool(self, name: str, args: dict, actions: list[dict]) -> tuple[str, bool]:
        """Run one tool call (or queue it for approval). Returns (output, is_error)."""
        tool = self.tool_map.get(name)
        try:
            if tool is None:
                raise ToolError(f"Unknown tool {name}.")
            if tool.requires_approval(self.ctx, args):
                if tool.prepare:
                    args = tool.prepare(self.ctx, args)  # freeze details, e.g. the exact number
                summary = tool.describe(self.ctx, args)
                if self.approver is not None:
                    output = tool.handler(self.ctx, args) if self.approver(tool, args, summary) \
                        else "The user declined this action."
                else:
                    action_id = self.ctx.db.execute(
                        "INSERT INTO pending_actions (tool, input, summary, created_at) VALUES (?, ?, ?, ?)",
                        (tool.name, json.dumps(args), summary, utcnow()),
                    )
                    actions.append({"id": action_id, "summary": summary})
                    output = (f"Waiting for the user's approval (action #{action_id}). They now see "
                              "Approve / Deny buttons. Briefly tell them what you're about to do; "
                              "don't call this tool again for it.")
            else:
                output = tool.handler(self.ctx, args)
            return output or "(no output)", False
        except ToolError as exc:
            return str(exc), True
        except Exception as exc:
            log.exception("Tool %s failed", name)
            return f"The tool failed: {type(exc).__name__}: {exc}", True

    def _save(self) -> None:
        self.ctx.db.save_conversation(self.conversation_id, self.messages)


def resolve_action(ctx: Context, action_id: int, approve: bool) -> tuple[dict, str]:
    """Approve (run) or deny a queued action. Returns (action row, result text)."""
    action = ctx.db.one("SELECT * FROM pending_actions WHERE id = ?", (action_id,))
    if not action:
        raise ToolError(f"No action #{action_id}.")
    if action["status"] != "pending":
        raise ToolError(f"Action #{action_id} was already {action['status']}.")
    # Claim it atomically so a double-click can't run it twice.
    new_status = "approved" if approve else "denied"
    if not ctx.db.execute(
        "UPDATE pending_actions SET status = ? WHERE id = ? AND status = 'pending'", (new_status, action_id)
    ):
        raise ToolError(f"Action #{action_id} was already handled.")
    if not approve:
        result = "Denied by the user."
    else:
        from jarvis.tools import REGISTRY, load_all

        load_all()
        tool = REGISTRY[action["tool"]]
        try:
            result = tool.handler(ctx, json.loads(action["input"]))
        except Exception as exc:
            result = f"Failed: {exc}"
    ctx.db.execute("UPDATE pending_actions SET result = ? WHERE id = ?", (result, action_id))
    return action, result


ClaudeBrain = Brain


def create_brain(ctx: Context, **kwargs: Any) -> Brain:
    """The brain for the configured AI provider (JARVIS_PROVIDER: gemini or claude)."""
    if ctx.settings.provider == "gemini":
        from jarvis.gemini_brain import GeminiBrain

        return GeminiBrain(ctx, **kwargs)
    return Brain(ctx, **kwargs)
