import time

import pytest
from fastapi.testclient import TestClient

from jarvis.brain import Brain
from jarvis.server import create_app
from jarvis.telegram import TelegramBot
from tests.conftest import FakeClaude, response, text, tool_use

OWNER, STRANGER = 4242, 999


class FakeResponse:
    def __init__(self, data=None, content=b""):
        self.data, self.content = data, content
        self.headers = {"content-type": "application/json"}
        self.status_code = 200

    def json(self):
        return self.data

    def raise_for_status(self):
        pass


class FakeTelegramAPI:
    def __init__(self):
        self.calls = []

    def post(self, url, json):
        method = url.rsplit("/", 1)[-1]
        self.calls.append((method, json))
        results = {"getMe": {"username": "jad_jarvis_bot"}, "getFile": {"file_path": "docs/f.txt", "file_size": 20},
                   "getWebhookInfo": {"url": ""}}
        return FakeResponse({"ok": True, "result": results.get(method, True)})

    def get(self, url):
        self.calls.append(("download", url))
        return FakeResponse(content=b"meeting notes: launch on Tuesday")

    def sent(self):
        return [p["text"] for m, p in self.calls if m == "sendMessage"]


@pytest.fixture
def api():
    return FakeTelegramAPI()


def make_bot(ctx, api, *responses):
    ctx.settings.telegram_bot_token = "123:ABC"
    claude = FakeClaude(*responses)
    bot = TelegramBot(ctx, lambda **kw: Brain(ctx, client=claude, **kw), client=api)
    return bot, claude


def msg(chat, text, update_id=None, **extra):
    return {"update_id": update_id or int(time.time() * 1000) % 10**9 + chat,
            "message": {"chat": {"id": chat, "type": "private"}, "from": {"id": chat}, "text": text, **extra}}


def test_linking_needs_the_code(ctx, api):
    bot, _ = make_bot(ctx, api)
    code = bot.new_link_code()
    bot.handle(msg(STRANGER, "/start 000000" if code != "000000" else "/start 111111", 1))
    assert bot.owner_chat is None and "private assistant" in api.sent()[-1]
    bot.handle(msg(OWNER, f"/start {code}", 2))
    assert bot.owner_chat == OWNER and api.sent()[-1].startswith("Linked.")
    # The code works once only.
    bot.handle(msg(STRANGER, f"/start {code}", 3))
    assert bot.owner_chat == OWNER


def test_expired_code_is_refused(ctx, api):
    bot, _ = make_bot(ctx, api)
    code = bot.new_link_code()
    ctx.db.set_kv("telegram_link_code", f"{code}:{int(time.time()) - 1}")
    bot.handle(msg(OWNER, f"/start {code}", 1))
    assert bot.owner_chat is None


def test_owner_chats_and_strangers_are_ignored(ctx, api):
    bot, claude = make_bot(ctx, api, response(text("Good evening, Tony.")))
    ctx.db.set_kv("telegram_chat_id", str(OWNER))
    bot.handle(msg(STRANGER, "what's the owner's address?", 1))
    assert api.sent() == [] and claude.requests == []
    bot.handle(msg(OWNER, "hello", 2))
    assert api.sent() == ["Good evening, Tony."]
    bot.handle(msg(OWNER, "hello", 2))  # Telegram retried the same update
    assert len(claude.requests) == 1
    group = msg(OWNER, "hi", 3)
    group["message"]["chat"]["type"] = "group"
    bot.handle(group)
    assert len(claude.requests) == 1


def test_documents_are_read(ctx, api):
    bot, claude = make_bot(ctx, api, response(text("The launch is on Tuesday.")))
    ctx.db.set_kv("telegram_chat_id", str(OWNER))
    update = msg(OWNER, "", 1, document={"file_id": "F1", "file_name": "notes.txt", "mime_type": "text/plain"})
    update["message"].pop("text")
    update["message"]["caption"] = "when is the launch?"
    bot.handle(update)
    sent = claude.requests[0]["messages"][-1]["content"][-1]["text"]
    assert "when is the launch?" in sent and "launch on Tuesday" in sent and '<attached_file name="notes.txt">' in sent
    assert api.sent() == ["The launch is on Tuesday."]


def test_approvals_use_buttons(phone_ctx, api, twilio):
    bot, claude = make_bot(
        phone_ctx, api,
        response(tool_use("call_contact", {"who": "+15559998888", "message": "running late"})),
        response(text("I'll call them once you approve.")),
        response(text("Done, the call is on its way.")),
    )
    phone_ctx.db.set_kv("telegram_chat_id", str(OWNER))
    bot.handle(msg(OWNER, "call +15559998888 and say I'm running late", 1))
    buttons = [p for m, p in api.calls if m == "sendMessage" and "reply_markup" in p]
    assert len(buttons) == 1 and buttons[0]["text"].startswith("Approval needed")
    approve = buttons[0]["reply_markup"]["inline_keyboard"][0][0]["callback_data"]
    # A stranger can't press it.
    bot.handle({"update_id": 2, "callback_query": {"id": "q0", "data": approve, "from": {"id": STRANGER},
                                                   "message": {"chat": {"id": STRANGER}, "message_id": 5}}})
    assert twilio.calls_made == []
    bot.handle({"update_id": 3, "callback_query": {"id": "q1", "data": approve, "from": {"id": OWNER},
                                                   "message": {"chat": {"id": OWNER}, "message_id": 5}}})
    assert len(twilio.calls_made) == 1
    assert api.sent()[-1] == "Done, the call is on its way."


def test_long_replies_are_split(ctx, api):
    bot, _ = make_bot(ctx, api)
    bot.send(OWNER, "x" * 9000)
    assert [len(t) for t in api.sent()] == [4000, 4000, 1000]


def test_notifications_go_to_the_linked_chat(ctx, api, monkeypatch):
    bot, _ = make_bot(ctx, api)
    monkeypatch.setattr("jarvis.telegram.threading.Thread",
                        lambda target, name=None, daemon=None: type("T", (), {"start": lambda self: target()})())
    bot.forward({"kind": "reminder", "message": "Reminder: Gym"})
    assert api.sent() == []  # not linked yet
    ctx.db.set_kv("telegram_chat_id", str(OWNER))
    bot.forward({"kind": "chat", "message": "not this"})
    bot.forward({"kind": "reminder", "message": "Reminder: Gym"})
    assert api.sent() == ["⏰ Reminder: Gym"]


def test_webhook_needs_the_secret(ctx, monkeypatch):
    app = create_app(ctx, brain_factory=lambda **kw: Brain(ctx, client=FakeClaude(), **kw))
    client = TestClient(app, base_url="http://localhost", client=("203.0.113.9", 5000))
    assert client.post("/telegram/webhook", json={}).status_code == 404  # Telegram not set up
    ctx.settings.telegram_bot_token = "123:ABC"
    ctx.db.set_kv("telegram_secret", "right-secret")
    handled = []
    monkeypatch.setattr(TelegramBot, "handle_async", lambda self, update: handled.append(update))
    assert client.post("/telegram/webhook", json={"update_id": 1}).status_code == 404
    assert client.post("/telegram/webhook", json={"update_id": 1},
                       headers={"X-Telegram-Bot-Api-Secret-Token": "wrong"}).status_code == 404
    ok = client.post("/telegram/webhook", json={"update_id": 1},
                     headers={"X-Telegram-Bot-Api-Secret-Token": "right-secret"})
    assert ok.status_code == 200 and handled == [{"update_id": 1}]


def test_link_endpoint(ctx, monkeypatch):
    app = create_app(ctx, brain_factory=lambda **kw: Brain(ctx, client=FakeClaude(), **kw))
    client = TestClient(app, base_url="http://localhost", client=("127.0.0.1", 5000))
    assert client.post("/api/telegram/link").status_code == 404
    assert client.get("/api/status").json()["telegram"] == {"enabled": False, "linked": False}
    ctx.settings.telegram_bot_token = "123:ABC"
    monkeypatch.setattr(TelegramBot, "username", lambda self: "jad_jarvis_bot")
    out = client.post("/api/telegram/link").json()
    assert out["link"] == f"https://t.me/jad_jarvis_bot?start={out['code']}" and len(out["code"]) == 6
    assert client.get("/api/status").json()["telegram"]["enabled"] is True
