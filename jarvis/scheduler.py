"""Background thread that fires due reminders."""

from __future__ import annotations

import json
import logging
import threading
import time
from typing import Callable
from datetime import datetime, timezone

from jarvis.tools import Context

log = logging.getLogger("jarvis.scheduler")


def fire_due_reminders(ctx: Context) -> int:
    now = datetime.now(timezone.utc).isoformat(timespec="seconds")
    due = ctx.db.query(
        "SELECT * FROM reminders WHERE status = 'pending' AND due_at <= ? ORDER BY due_at", (now,)
    )
    for r in due:
        # Claim it first so a reminder never fires twice.
        if not ctx.db.execute(
            "UPDATE reminders SET status = 'fired' WHERE id = ? AND status = 'pending'", (r["id"],)
        ):
            continue
        channels = json.loads(r["notify_by"])
        text = f"Reminder: {r['message']}"
        ctx.notifier.publish("reminder", text, id=r["id"])
        try:
            if "call" in channels:
                ctx.phone.call_owner(text)
            if "sms" in channels:
                ctx.phone.text_owner(text)
        except Exception as exc:
            log.exception("Phone alert for reminder #%s failed", r["id"])
            ctx.notifier.publish("error", f"Couldn't phone you about reminder #{r['id']}: {exc}")
    return len(due)


class ReminderLoop:
    """Fires due reminders every few seconds, and runs ``on_tick`` (e.g. the morning
    briefing check) about once a minute."""

    def __init__(self, ctx: Context, interval: float | None = None,
                 on_tick: Callable[[], None] | None = None, tick_every: float = 60.0):
        self.ctx = ctx
        self.interval = interval or ctx.db.poll_interval
        self.on_tick = on_tick
        self.tick_every = tick_every
        self._last_tick = 0.0
        self._stop = threading.Event()
        self._thread = threading.Thread(target=self._run, name="reminders", daemon=True)

    def start(self) -> None:
        self._thread.start()

    def stop(self) -> None:
        self._stop.set()

    def _run(self) -> None:
        while not self._stop.is_set():
            try:
                fire_due_reminders(self.ctx)
            except Exception:
                log.exception("Reminder loop error")
            if self.on_tick and time.monotonic() - self._last_tick >= self.tick_every:
                self._last_tick = time.monotonic()
                try:
                    self.on_tick()
                except Exception:
                    log.exception("Scheduled task error")
            self._stop.wait(self.interval)
