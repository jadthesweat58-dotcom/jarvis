from __future__ import annotations

from dataclasses import replace
from types import SimpleNamespace

import pytest

from jarvis.config import Settings
from jarvis.db import Database
from jarvis.notify import Notifier
from jarvis.phone import Phone
from jarvis.tools import Context


class Block(SimpleNamespace):
    def model_dump(self, **_):
        return {k: v for k, v in vars(self).items() if v is not None}


def text(t):
    return Block(type="text", text=t)


def tool_use(name, input, id="tu_1"):
    return Block(type="tool_use", id=id, name=name, input=input)


def response(*blocks, stop_reason=None):
    if stop_reason is None:
        stop_reason = "tool_use" if any(b.type == "tool_use" for b in blocks) else "end_turn"
    return SimpleNamespace(content=list(blocks), stop_reason=stop_reason)


class FakeClaude:
    """Stands in for anthropic.Anthropic(); replays scripted responses."""

    def __init__(self, *responses):
        self.responses = list(responses)
        self.requests = []
        self.beta = SimpleNamespace(messages=SimpleNamespace(create=self._create))

    def _create(self, **params):
        # Snapshot the messages: the brain keeps appending to the same list.
        self.requests.append({**params, "messages": [dict(m) for m in params["messages"]]})
        return self.responses.pop(0)


class FakeTwilio:
    def __init__(self):
        self.calls_made, self.texts_sent = [], []
        self.calls = SimpleNamespace(create=self._call)
        self.messages = SimpleNamespace(create=self._text)

    def _call(self, **kw):
        self.calls_made.append(kw)
        return SimpleNamespace(sid=f"CA{len(self.calls_made)}")

    def _text(self, **kw):
        self.texts_sent.append(kw)
        return SimpleNamespace(sid=f"SM{len(self.texts_sent)}")


@pytest.fixture
def settings(tmp_path):
    return replace(
        Settings(),
        provider="claude",
        anthropic_api_key="test",
        gemini_api_key="",
        my_name="Tony",
        timezone="UTC",
        home_city="",
        mode="cloud",
        model="claude-opus-5",
        effort="medium",
        access_token="",
        data_dir=tmp_path,
        files_root=tmp_path,
        twilio_account_sid="",
        twilio_auth_token="",
        twilio_phone_number="",
        my_phone_number="",
        public_base_url="",
    )


@pytest.fixture
def twilio():
    return FakeTwilio()


@pytest.fixture
def ctx(settings, twilio):
    db = Database(":memory:")
    return Context(db=db, settings=settings, notifier=Notifier(),
                   phone=Phone(settings, db, client_factory=lambda: twilio))


@pytest.fixture
def phone_ctx(ctx):
    """A context with Twilio configured."""
    s = ctx.settings
    s.twilio_account_sid, s.twilio_auth_token = "AC123", "secret"
    s.twilio_phone_number, s.my_phone_number = "+15550000000", "+15551112222"
    return ctx
