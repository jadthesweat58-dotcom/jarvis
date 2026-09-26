import pytest
from fastapi.testclient import TestClient
from twilio.request_validator import RequestValidator

from jarvis.brain import Brain
from jarvis.server import create_app
from tests.conftest import FakeClaude, response, text, tool_use


def make_client(ctx, claude, host="127.0.0.1"):
    app = create_app(ctx, brain_factory=lambda **kw: Brain(ctx, client=claude, **kw))
    return TestClient(app, client=(host, 5000))


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
    assert client.get("/api/status?token=s3cret").status_code == 200


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
    ctx.settings.public_base_url = "http://testserver"
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
    ctx.settings.public_base_url = "http://testserver"
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
    ctx.settings.public_base_url = "http://testserver"
    client = make_client(ctx, FakeClaude())
    r = signed_post(client, ctx, "/twilio/voice", {"From": "+15553334444", "CallSid": "CA7"})
    assert "take a message" in r.text
