"""A running tally of what Jarvis uses: AI calls and tokens, and voice characters.

Stored per local day so the dashboard can show "today" and "this month" and
warn before the ElevenLabs monthly quota runs out.
"""

from __future__ import annotations

import logging
from datetime import datetime
from typing import Any

from jarvis.tools import Context

log = logging.getLogger("jarvis.usage")

KINDS = ("ai_calls", "ai_tokens_in", "ai_tokens_out", "tts_chars")


def record(ctx: Context, amounts: dict[str, int]) -> None:
    """Add to today's totals. Never raises: a tally must not break a reply."""
    day = datetime.now(ctx.settings.tz).date().isoformat()
    for kind, amount in amounts.items():
        if not amount:
            continue
        try:
            ctx.db.execute(
                "INSERT INTO usage_log (day, kind, amount) VALUES (?, ?, ?) "
                "ON CONFLICT(day, kind) DO UPDATE SET amount = usage_log.amount + excluded.amount",
                (day, kind, int(amount)),
            )
        except Exception:
            log.warning("Couldn't record usage", exc_info=True)


def summary(ctx: Context) -> dict[str, Any]:
    today = datetime.now(ctx.settings.tz).date()
    rows = ctx.db.query("SELECT day, kind, amount FROM usage_log WHERE day >= ?",
                        (today.replace(day=1).isoformat(),))
    day_totals = {k: 0 for k in KINDS}
    month_totals = {k: 0 for k in KINDS}
    for r in rows:
        if r["kind"] not in month_totals:
            continue
        month_totals[r["kind"]] += int(r["amount"] or 0)
        if r["day"] == today.isoformat():
            day_totals[r["kind"]] += int(r["amount"] or 0)
    quota = ctx.settings.elevenlabs_monthly_chars
    return {"today": day_totals, "month": month_totals, "tts_quota": quota,
            "tts_left": max(quota - month_totals["tts_chars"], 0) if quota else None}
