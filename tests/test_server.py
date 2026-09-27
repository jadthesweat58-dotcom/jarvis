import pytest
from fastapi.testclient import TestClient
from twilio.request_validator import RequestValidator

from jarvis.brain import Brain
from jarvis.server import create_app
from tests.conftest import FakeClaude, response, text, tool_use


def make_client(ctx, claude, host="127.0.0.1"):
    app = create_app(ctx, brain_factory=lambda **kw: Brain(ctx, client=claude, **kw))
    return TestClient(app, base_url="http://localhost", client=(host, 5000))


def test_chat_from_localhost_without_token(ctx):
    client = make_client(ctx, FakeClaude(response(text("Hello, Tony."))))
    with client:
        assert client.get("/").status_code == 200
        assert client.get("/api/status").json()["mode"] == "cloud"
        assert client.post("/api/chat", json={"text": "hi"}).json() == {"reply": "Hello, Tony.", "actions": []}


def test_remote_access_needs_token(ctx):
    client = make_client(ctx, FakeClaude(), host="203.0.113.9")
    assert client.get("/api/status").status_code == 401
    ctx.settings.access_token = "s3cret"
    assert client.get("/api/status").status_code == 401
    assert client.get("/api/status", headers={"Authorization": "Bearer wrong"}).status_code == 401
    assert client.get("/api/status", headers={"Authorization": "Bearer s3cret"}).status_code == 200
    # Tokens in URLs end up in logs, so they're only accepted for the event stream.
    assert client.get("/api/status?token=s3cret").status_code == 401


def test_blocks_dns_rebinding_and_cross_site_requests(ctx):
    client = make_client(ctx, FakeClaude())
    assert client.get("/api/status").status_code == 200
    assert client.get("/api/status", headers={"Host": "evil.example"}).status_code == 401
    assert client.post("/api/reset", headers={"Origin": "https://evil.example"}).status_code == 403
    assert client.post("/api/reset", headers={"Origin": "http://localhost"}).status_code == 200


def test_phone_webhooks_are_off_without_twilio(ctx):
    client = make_client(ctx, FakeClaude(), host="203.0.113.9")
    assert client.post("/twilio/voice", data={"From": "+15551112222"}).status_code == 404
    assert client.post("/twilio/gather?call_id=1", data={"SpeechResult": "hi"}).status_code == 404


def test_approval_flow_over_http(phone_ctx, twilio):
    claude = FakeClaude(
        response(tool_use("call_contact", {"who": "+15559998888", "message": "hello"})),
        response(text("Awaiting your approval.")),
        response(text("Calling now.")),
    )
    client = make_client(phone_ctx, claude)
    data = client.post("/api/chat", json={"text": "call them"}).json()
    action_id = data["actions"][0]["id"]
    assert client.get("/api/dashboard").json()["actions"][0]["id"] == action_id
    out = client.post(f"/api/actions/{action_id}", json={"approve": True}).json()
    assert out["reply"] == "Calling now." and "Calling" in out["result"]
    assert len(twilio.calls_made) == 1
    assert client.post(f"/api/actions/{action_id}", json={"approve": True}).status_code == 409


def signed_post(client, ctx, path, form):
    url = ctx.settings.public_base_url + path
    sig = RequestValidator(ctx.settings.twilio_auth_token).compute_signature(url, form)
    return client.post(path, data=form, headers={"X-Twilio-Signature": sig})


def test_two_way_call_with_contact(phone_ctx, twilio):
    ctx = phone_ctx
    ctx.settings.public_base_url = "http://localhost"
    events = []
    ctx.notifier.subscribe(events.append)
    claude = FakeClaude(
        response(text("Of course, I'll tell him you'll be there at eight.")),
        response(text("Goodbye! [HANGUP]")),
    )
    client = make_client(ctx, claude)
    call_id = ctx.phone.call("+15559998888", "Dinner at 7?", contact_name="Pepper", conversation=True)

    # Unsigned webhooks are rejected.
    assert client.post(f"/twilio/voice?call_id={call_id}", data={}).status_code == 403

    r = signed_post(client, ctx, f"/twilio/voice?call_id={call_id}", {"CallSid": "CA1"})
    assert "Dinner at 7?" in r.text and "<Gather" in r.text
    r = signed_post(client, ctx, f"/twilio/gather?call_id={call_id}", {"SpeechResult": "Make it eight"})
    assert "eight" in r.text and "<Gather" in r.text
    # The contact's brain has no tools and is told the call's purpose.
    assert claude.requests[0]["tools"] == [] and "Dinner at 7?" in claude.requests[0]["system"]
    r = signed_post(client, ctx, f"/twilio/gather?call_id={call_id}", {"SpeechResult": "Thanks, bye"})
    assert "<Hangup" in r.text and "[HANGUP]" not in r.text

    signed_post(client, ctx, f"/twilio/status?call_id={call_id}", {"CallStatus": "completed"})
    assert events[-1]["kind"] == "call" and "Make it eight" in events[-1]["message"]
    assert "Make it eight" in ctx.db.one("SELECT body FROM notes")["body"]


def test_inbound_call_from_owner_gets_full_jarvis(phone_ctx):
    ctx = phone_ctx
    ctx.settings.public_base_url = "http://localhost"
    claude = FakeClaude(response(text("You have no reminders today.")))
    client = make_client(ctx, claude)
    r = signed_post(client, ctx, "/twilio/voice", {"From": "+15551112222", "CallSid": "CA9"})
    assert "Hello Tony" in r.text
    call_id = ctx.db.one("SELECT id FROM phone_calls")["id"]
    signed_post(client, ctx, f"/twilio/gather?call_id={call_id}", {"SpeechResult": "Any reminders?"})
    tools = {t["name"] for t in claude.requests[0]["tools"]}
    assert "set_reminder" in tools and "phone call" in claude.requests[0]["system"]


def test_inbound_call_from_stranger_takes_message(phone_ctx):
    ctx = phone_ctx
    ctx.settings.public_base_url = "http://localhost"
    events = []
    ctx.notifier.subscribe(events.append)
    claude = FakeClaude(response(text("Got it, I'll pass that on. Goodbye! [HANGUP]")))
    client = make_client(ctx, claude)
    r = signed_post(client, ctx, "/twilio/voice", {"From": "+15553334444", "CallSid": "CA7"})
    assert "take a message" in r.text
    call_id = ctx.db.one("SELECT id FROM phone_calls")["id"]
    r = signed_post(client, ctx, f"/twilio/gather?call_id={call_id}", {"SpeechResult": "It's Bob, call me back"})
    assert "<Hangup" in r.text
    assert "It's Bob, call me back" in events[-1]["message"]
    assert "It's Bob" in ctx.db.one("SELECT body FROM notes")["body"]
    # A later status webhook (matched by CallSid) doesn't report it twice.
    signed_post(client, ctx, "/twilio/status", {"CallSid": "CA7", "CallStatus": "completed"})
    assert len(events) == 1


def test_signature_accepts_https_behind_proxy(phone_ctx):
    ctx = phone_ctx  # PUBLIC_BASE_URL unset; the proxy terminated https
    client = make_client(ctx, FakeClaude())
    url = "https://localhost/twilio/voice"
    form = {"From": "+15553334444", "CallSid": "CA8"}
    sig = RequestValidator("secret").compute_signature(url, form)
    r = client.post("/twilio/voice", data=form, headers={"X-Twilio-Signature": sig, "X-Forwarded-Proto": "https"})
    assert r.status_code == 200 and 'action="https://localhost/twilio/gather' in r.text


def test_tasks_timeline_and_system(ctx):
    from datetime import datetime, timedelta, timezone

    client = make_client(ctx, FakeClaude())
    assert client.post("/api/todos", json={"task": "Ship HUD", "priority": "high"}).json()["ok"]
    assert client.post("/api/todos", json={"task": "Nap", "priority": "bogus"}).json()["ok"]
    assert client.post("/api/todos", json={"task": "  "}).status_code == 400
    tasks = client.get("/api/dashboard").json()["tasks"]
    assert [(t["task"], t["priority"], t["done"]) for t in tasks] == [("Ship HUD", "high", 0), ("Nap", "med", 0)]
    assert client.post(f"/api/todos/{tasks[0]['id']}", json={"done": True}).json() == {"ok": True}
    assert client.post("/api/todos/999", json={"done": True}).status_code == 404
    data = client.get("/api/dashboard").json()
    assert data["tasks"][-1]["task"] == "Ship HUD" and data["tasks"][-1]["done"] == 1
    assert data["counts"]["todos"] == 1 and data["counts"]["todos_done"] == 1

    soon = (datetime.now(timezone.utc) + timedelta(minutes=5)).isoformat(timespec="seconds")
    ctx.db.execute("INSERT INTO reminders (message, due_at, created_at) VALUES ('Standup', ?, 'x')", (soon,))
    timeline = client.get("/api/dashboard").json()["timeline"]
    assert timeline[0]["message"] == "Standup" and timeline[0]["status"] == "pending" and timeline[0]["time_local"]
    assert set(client.get("/api/system").json()) >= {"cpu", "ram"}
    assert client.get("/api/status").json()["started_at"]


def test_priority_column_added_to_old_databases(tmp_path):
    import sqlite3

    from jarvis.db import Database

    path = tmp_path / "old.db"
    old = sqlite3.connect(path)
    old.execute("CREATE TABLE todos (id INTEGER PRIMARY KEY AUTOINCREMENT, task TEXT NOT NULL, due TEXT, "
                "done INTEGER NOT NULL DEFAULT 0, created_at TEXT NOT NULL)")
    old.execute("INSERT INTO todos (task, created_at) VALUES ('old task', 'x')")
    old.commit()
    old.close()
    db = Database(path)
    assert db.one("SELECT task, priority FROM todos") == {"task": "old task", "priority": "med"}


class FakeElevenLabs:
    def __init__(self, status=200, body=b"ID3fake-mp3"):
        self.status, self.body, self.requests = status, body, []

    def handle(self, request):
        import httpx

        self.requests.append(request)
        if self.status != 200:
            return httpx.Response(self.status, json={"detail": {"status": "quota_exceeded" if self.status == 402 else "x",
                                                                  "message": "nope"}})
        return httpx.Response(200, content=self.body, headers={"content-type": "audio/mpeg"})


def voice_client(ctx, fake):
    import httpx

    from jarvis.voice import ElevenLabsVoice

    voice = ElevenLabsVoice(ctx.settings, client=httpx.Client(transport=httpx.MockTransport(fake.handle)))
    app = create_app(ctx, brain_factory=lambda **kw: Brain(ctx, client=FakeClaude(), **kw), voice=voice)
    return TestClient(app, base_url="http://localhost", client=("127.0.0.1", 5000))


def test_tts_off_until_configured(ctx):
    client = voice_client(ctx, FakeElevenLabs())
    assert client.get("/api/status").json()["tts"] == "browser"
    assert client.post("/api/tts", json={"text": "hi"}).status_code == 404


def test_tts_with_elevenlabs(ctx):
    import json

    ctx.settings.elevenlabs_api_key, ctx.settings.elevenlabs_voice_id = "el-key", "voice123"
    fake = FakeElevenLabs()
    client = voice_client(ctx, fake)
    assert client.get("/api/status").json()["tts"] == "elevenlabs"
    r = client.post("/api/tts", json={"text": "Good   evening,\n Jad."})
    assert r.status_code == 200 and r.headers["content-type"] == "audio/mpeg" and r.content == b"ID3fake-mp3"
    sent = fake.requests[0]
    assert sent.url.path == "/v1/text-to-speech/voice123" and sent.headers["xi-api-key"] == "el-key"
    assert json.loads(sent.content) == {"text": "Good evening, Jad.", "model_id": "eleven_flash_v2_5"}
    client.post("/api/tts", json={"text": "Good evening, Jad."})
    assert len(fake.requests) == 1  # repeated phrase came from the cache
    client.post("/api/tts", json={"text": "x" * 5000})
    assert len(json.loads(fake.requests[-1].content)["text"]) == 1000
    assert client.post("/api/tts", json={"text": "   "}).status_code == 502


def test_tts_errors_are_explained(ctx):
    ctx.settings.elevenlabs_api_key, ctx.settings.elevenlabs_voice_id = "bad", "voice123"
    for status, words in ((401, "API key"), (404, "voice"), (402, "quota")):
        r = voice_client(ctx, FakeElevenLabs(status=status)).post("/api/tts", json={"text": "hello"})
        assert r.status_code == 502 and words in r.json()["detail"]
