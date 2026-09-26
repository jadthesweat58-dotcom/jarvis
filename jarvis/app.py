"""Wires the pieces together: settings, database, notifier, phone."""

from __future__ import annotations

from jarvis.config import Settings, settings as default_settings
from jarvis.db import Database
from jarvis.notify import Notifier
from jarvis.phone import Phone
from jarvis.tools import Context


def build_context(settings: Settings | None = None, db: Database | None = None) -> Context:
    settings = settings or default_settings
    db = db or Database(settings.db_path)
    return Context(db=db, settings=settings, notifier=Notifier(), phone=Phone(settings, db))
