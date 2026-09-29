"""Phone and desktop notifications that arrive even when Jarvis isn't open (Web Push).

The browser gives Jarvis a private "subscription" address at its push service
(Apple, Google or Mozilla). Messages are encrypted for that browser and signed
with Jarvis's own VAPID key, which is made on first use and kept in the
database, so no account or API key is needed.
"""

from __future__ import annotations

import base64
import json
import logging
import threading
from typing import Any
from urllib.parse import urlsplit

from jarvis.db import utcnow
from jarvis.tools import Context

log = logging.getLogger("jarvis.push")

# Notifier events worth waking your phone for.
PUSH_KINDS = {"reminder", "briefing", "call", "error", "routine", "watch"}
TITLES = {"reminder": "⏰ Reminder", "briefing": "🌅 Morning briefing", "call": "📞 Phone call", "error": "⚠️ Jarvis",
          "routine": "🔁 Routine", "watch": "🔎 Watcher"}
_key_lock = threading.Lock()


def _b64url(data: bytes) -> str:
    return base64.urlsafe_b64encode(data).rstrip(b"=").decode()


def vapid_keys(ctx: Context) -> tuple[str, str]:
    """(private key PEM, public key for the browser), created once and stored."""
    with _key_lock:
        private_pem = ctx.db.get_kv("vapid_private_key")
        if not private_pem:
            from cryptography.hazmat.primitives import serialization
            from cryptography.hazmat.primitives.asymmetric import ec

            key = ec.generate_private_key(ec.SECP256R1())
            private_pem = key.private_bytes(serialization.Encoding.PEM, serialization.PrivateFormat.PKCS8,
                                            serialization.NoEncryption()).decode()
            # Another server sharing the database may have stored a key first: keep that one.
            ctx.db.execute("INSERT INTO kv (key, value) VALUES ('vapid_private_key', ?) ON CONFLICT(key) DO NOTHING",
                           (private_pem,))
            private_pem = ctx.db.get_kv("vapid_private_key") or private_pem
    from cryptography.hazmat.primitives import serialization

    key = serialization.load_pem_private_key(private_pem.encode(), password=None)
    public = key.public_key().public_bytes(serialization.Encoding.X962,
                                           serialization.PublicFormat.UncompressedPoint)
    return private_pem, _b64url(public)


def public_key(ctx: Context) -> str:
    return vapid_keys(ctx)[1]


def save_subscription(ctx: Context, sub: dict[str, Any]) -> None:
    endpoint = str(sub.get("endpoint") or "")
    keys = sub.get("keys") or {}
    if not (endpoint.startswith("https://") and keys.get("p256dh") and keys.get("auth")):
        raise ValueError("That isn't a valid push subscription.")
    from jarvis.safeurl import UnsafeURL, check_url

    try:
        check_url(endpoint)  # Jarvis will POST here, so it must be on the public internet
    except UnsafeURL as exc:
        raise ValueError(str(exc)) from exc
    data = json.dumps({"endpoint": endpoint, "keys": {"p256dh": keys["p256dh"], "auth": keys["auth"]}})
    ctx.db.execute("INSERT INTO push_subscriptions (endpoint, data, created_at) VALUES (?, ?, ?) "
                   "ON CONFLICT(endpoint) DO UPDATE SET data = excluded.data", (endpoint, data, utcnow()))


def remove_subscription(ctx: Context, endpoint: str) -> bool:
    return bool(ctx.db.execute("DELETE FROM push_subscriptions WHERE endpoint = ?", (endpoint,)))


def count(ctx: Context) -> int:
    row = ctx.db.one("SELECT COUNT(*) AS n FROM push_subscriptions")
    return int(row["n"] or 0) if row else 0


def _subject(ctx: Context) -> str:
    # Push services want a way to contact the sender: a https URL or a mailto: address.
    base = ctx.settings.public_base_url
    return base if base.startswith("https://") else "mailto:jarvis@example.com"


def send_all(ctx: Context, title: str, body: str, *, tag: str = "jarvis", url: str = "/",
             sender: Any = None) -> int:
    """Send a notification to every subscribed browser. Returns how many accepted it.
    Subscriptions the push service says are gone (404/410) are removed."""
    subs = ctx.db.query("SELECT endpoint, data FROM push_subscriptions")
    if not subs:
        return 0
    if sender is None:
        from pywebpush import webpush as sender
    from py_vapid import Vapid02

    private_pem, _ = vapid_keys(ctx)
    vapid = Vapid02.from_pem(private_pem.encode())
    payload = json.dumps({"title": title, "body": body[:1500], "tag": tag, "url": url})
    delivered = 0
    for row in subs:
        info = json.loads(row["data"])
        try:
            sender(subscription_info=info, data=payload, vapid_private_key=vapid,
                   vapid_claims={"sub": _subject(ctx), "aud": _audience(info["endpoint"])},
                   ttl=12 * 3600, headers={"Urgency": "high"}, timeout=10)
            delivered += 1
        except Exception as exc:
            status = getattr(getattr(exc, "response", None), "status_code", None)
            if status in (404, 410):
                remove_subscription(ctx, row["endpoint"])  # that browser unsubscribed or was reset
            else:
                log.warning("Push to %s failed: %s", urlsplit(row["endpoint"]).hostname, exc)
    return delivered


def _audience(endpoint: str) -> str:
    parts = urlsplit(endpoint)
    return f"{parts.scheme}://{parts.netloc}"


def forward(ctx: Context, event: dict[str, Any]) -> None:
    """Notifier listener: push the events that matter, in the background."""
    if event.get("kind") not in PUSH_KINDS or not event.get("message"):
        return
    kind = event["kind"]
    tag = f"{kind}-{event.get('id', '')}" if event.get("id") is not None else kind

    def run() -> None:
        try:
            send_all(ctx, TITLES.get(kind, "Jarvis"), event["message"], tag=tag)
        except Exception:
            log.exception("Push notification failed")

    threading.Thread(target=run, name="push", daemon=True).start()
