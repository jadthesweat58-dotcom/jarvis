"""Tiny thread-safe publish/subscribe hub for pushing events (reminders,
call summaries) to whoever is listening: the web UI, the terminal, etc."""

from __future__ import annotations

import threading
from datetime import datetime, timezone
from typing import Callable

Event = dict
Subscriber = Callable[[Event], None]


class Notifier:
    def __init__(self) -> None:
        self._subscribers: list[Subscriber] = []
        self._lock = threading.Lock()

    def subscribe(self, callback: Subscriber) -> Callable[[], None]:
        with self._lock:
            self._subscribers.append(callback)

        def unsubscribe() -> None:
            with self._lock:
                if callback in self._subscribers:
                    self._subscribers.remove(callback)

        return unsubscribe

    def publish(self, kind: str, message: str, **extra) -> None:
        at = datetime.now(timezone.utc).isoformat(timespec="milliseconds")
        event = {"kind": kind, "message": message, "at": at, **extra}
        with self._lock:
            subscribers = list(self._subscribers)
        for callback in subscribers:
            try:
                callback(event)
            except Exception:  # one broken listener must not block the others
                pass

    @property
    def has_listeners(self) -> bool:
        with self._lock:
            return bool(self._subscribers)
