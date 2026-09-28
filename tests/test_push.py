import base64
import json
import os
import socket
import threading

import pytest
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import ec
from fastapi.testclient import TestClient

from jarvis import push, safeurl
from jarvis.brain import Brain
from jarvis.server import create_app
from tests.conftest import FakeClaude


def b64(data: bytes) -> str:
    return base64.urlsafe_b64encode(data).rstrip(b"=").decode()


@pytest.fixture(autouse=True)
def public_dns(monkeypatch):
    def fake(host, port, *a, **kw):
        ip = "10.0.0.9" if host == "internal.example" else "142.250.1.1"
        return [(socket.AF_INET, socket.SOCK_STREAM, 6, "", (ip, port))]

    monkeypatch.setattr(safeurl.socket, "getaddrinfo", fake)


def browser():
    """A fake browser subscription: (subscription dict, private key, auth secret)."""
    key = ec.generate_private_key(ec.SECP256R1())
    pub = key.public_key().public_bytes(serialization.Encoding.X962, serialization.PublicFormat.UncompressedPoint)
    auth = os.urandom(16)
    endpoint = f"https://fcm.googleapis.com/fcm/send/{b64(os.urandom(8))}"
    return {"endpoint": endpoint, "keys": {"p256dh": b64(pub), "auth": b64(auth)}}, key, auth


def test_vapid_key_is_made_once(ctx):
    first = push.public_key(ctx)
    assert push.public_key(ctx) == first
    assert len(base64.urlsafe_b64decode(first + "==")) == 65  # an uncompressed P-256 point


def test_subscriptions_are_validated_and_upserted(ctx):
    sub, _, _ = browser()
    push.save_subscription(ctx, sub)
    push.save_subscription(ctx, sub)
    assert push.count(ctx) == 1
    for bad in ({"endpoint": "http://fcm.googleapis.com/x", "keys": sub["keys"]},
                {"endpoint": "https://internal.example/x", "keys": sub["keys"]},
                {"endpoint": sub["endpoint"], "keys": {}}):
        with pytest.raises(ValueError):
            push.save_subscription(ctx, bad)
    assert push.remove_subscription(ctx, sub["endpoint"]) and push.count(ctx) == 0


def test_notifications_are_encrypted_for_the_browser(ctx, monkeypatch):
    """Real pywebpush encryption, decrypted the way the browser would."""
    import http_ece
    import pywebpush

    sub, key, auth = browser()
    push.save_subscription(ctx, sub)
    ctx.settings.public_base_url = "https://jarvis.example.com"
    sent = []

    class Ok:
        status_code = 201
        text = ""
        headers: dict = {}

    monkeypatch.setattr(pywebpush.requests, "post",
                        lambda url, data=None, headers=None, timeout=None, **kw: sent.append((url, data, headers)) or Ok())
    assert push.send_all(ctx, "⏰ Reminder", "Call Mom") == 1
    url, body, headers = sent[0]
    assert url == sub["endpoint"] and headers["content-encoding"] == "aes128gcm"
    assert headers["authorization"].startswith("vapid t=") and f"k={push.public_key(ctx)}" in headers["authorization"]
    payload = json.loads(http_ece.decrypt(body, private_key=key, auth_secret=auth, version="aes128gcm"))
    assert payload == {"title": "⏰ Reminder", "body": "Call Mom", "tag": "jarvis", "url": "/"}


def test_gone_subscriptions_are_removed(ctx):
    alive, _, _ = browser()
    gone, _, _ = browser()
    push.save_subscription(ctx, alive)
    push.save_subscription(ctx, gone)

    class Gone(Exception):
        response = type("R", (), {"status_code": 410})()

    def sender(subscription_info, **kw):
        if subscription_info["endpoint"] == gone["endpoint"]:
            raise Gone("unsubscribed")

    assert push.send_all(ctx, "t", "b", sender=sender) == 1
    assert [r["endpoint"] for r in ctx.db.query("SELECT endpoint FROM push_subscriptions")] == [alive["endpoint"]]


def test_reminders_are_pushed(ctx, monkeypatch):
    got, done = [], threading.Event()
    monkeypatch.setattr(push, "send_all", lambda c, title, body, tag: (got.append((title, body, tag)), done.set()))
    push.forward(ctx, {"kind": "chat", "message": "ignored"})
    push.forward(ctx, {"kind": "reminder", "message": "Reminder: Gym", "id": 7})
    assert done.wait(2)
    assert got == [("⏰ Reminder", "Reminder: Gym", "reminder-7")]


def test_push_endpoints(ctx):
    app = create_app(ctx, brain_factory=lambda **kw: Brain(ctx, client=FakeClaude(), **kw))
    client = TestClient(app, base_url="http://localhost", client=("127.0.0.1", 5000))
    key = client.get("/api/push/key").json()
    assert key["subscribers"] == 0 and key["key"] == push.public_key(ctx)
    assert client.post("/api/push/test").status_code == 409  # nobody subscribed yet
    sub, _, _ = browser()
    assert client.post("/api/push/subscribe", json=sub).json() == {"ok": True}
    assert client.get("/api/push/key").json()["subscribers"] == 1
    assert client.post("/api/push/subscribe", json={"endpoint": "https://internal.example/x", "keys": sub["keys"]}).status_code == 400
    assert client.post("/api/push/unsubscribe", json={"endpoint": sub["endpoint"]}).json() == {"ok": True}
    # Everything needs the owner's token when one is set.
    ctx.settings.access_token = "tok"
    assert client.get("/api/push/key").status_code == 401
    # The service worker and manifest are public (they hold nothing private).
    sw = client.get("/sw.js")
    assert sw.status_code == 200 and "showNotification" in sw.text and sw.headers["service-worker-allowed"] == "/"
    assert client.get("/manifest.webmanifest").json()["start_url"] == "/"
