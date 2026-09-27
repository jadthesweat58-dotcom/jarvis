"""Chat with Jarvis in the terminal:  python -m jarvis.cli"""

from __future__ import annotations

import sys

from jarvis.app import build_context
from jarvis.brain import create_brain
from jarvis.scheduler import ReminderLoop
from jarvis.tools import Tool

BLUE, DIM, YELLOW, RESET = "\033[96m", "\033[2m", "\033[93m", "\033[0m"


def ask_approval(tool: Tool, args: dict, summary: str) -> bool:
    answer = input(f"{YELLOW}Jarvis wants to: {summary}\nAllow? [y/N] {RESET}").strip().lower()
    return answer in ("y", "yes")


def main() -> None:
    ctx = build_context()
    ctx.notifier.subscribe(lambda e: print(f"\n{YELLOW}🔔 {e['message']}{RESET}\nYou: ", end="", flush=True))
    ReminderLoop(ctx).start()
    brain = create_brain(ctx, conversation_id="cli", approver=ask_approval)
    mode = "local (computer control on)" if ctx.settings.is_local else "cloud (computer control off)"
    print(f"{BLUE}J.A.R.V.I.S. online.{RESET} {DIM}Brain: {ctx.settings.provider_name} "
          f"({ctx.settings.model}). Mode: {mode}. Type 'new' for a fresh "
          f"conversation, 'quit' to exit.{RESET}")
    while True:
        try:
            text = input("You: ").strip()
        except (EOFError, KeyboardInterrupt):
            print()
            break
        if not text:
            continue
        if text.lower() in ("quit", "exit", "bye"):
            break
        if text.lower() == "new":
            brain.reset()
            print(f"{DIM}Started a new conversation.{RESET}")
            continue
        try:
            reply = brain.chat(text)
        except Exception as exc:  # show the problem, keep the session alive
            print(f"{YELLOW}Error: {exc}{RESET}", file=sys.stderr)
            continue
        print(f"{BLUE}Jarvis:{RESET} {reply.text}")
    print(f"{DIM}Goodbye, {ctx.settings.my_name}.{RESET}")


if __name__ == "__main__":
    main()
