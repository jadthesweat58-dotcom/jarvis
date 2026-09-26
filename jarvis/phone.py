"""Phone calls and text messages through Twilio."""

from __future__ import annotations

import re
from typing import TYPE_CHECKING, Any, Callable

from twilio.twiml.voice_response import VoiceResponse

from jarvis.db import utcnow

if TYPE_CHECKING:
    from jarvis.config import Settings
    from jarvis.db import Database

# Twilio's British "Brian" voice sounds suitably Jarvis-like.
VOICE = "Polly.Brian"
E164 = re.compile(r"^\+[1-9]\d{6,14}$")


class PhoneError(Exception):
    pass


def normalize_number(number: str) -> str:
    cleaned = re.sub(r"[\s().-]", "", number or "")
    if cleaned.startswith("00"):
        cleaned = "+" + cleaned[2:]
    if not E164.match(cleaned):
        raise PhoneError(
            f"'{number}' isn't a full international number. It must start with + and the "
            "country code, e.g. +15551234567."
        )
    return cleaned


def say(response: VoiceResponse, text: str) -> None:
    response.say(text, voice=VOICE)


class Phone:
    def __init__(
        self,
        settings: "Settings",
        db: "Database",
        client_factory: Callable[[], Any] | None = None,
    ):
        self.settings = settings
        self.db = db
        self._client_factory = client_factory
        self._client = None

    @property
    def client(self):
        if not self.settings.twilio_enabled:
            raise PhoneError("Phone features aren't set up. Add your Twilio keys to .env.")
        if self._client is None:
            if self._client_factory:
                self._client = self._client_factory()
            else:
                from twilio.rest import Client

                self._client = Client(self.settings.twilio_account_sid, self.settings.twilio_auth_token)
        return self._client

    @property
    def can_converse(self) -> bool:
        """Two-way calls need Twilio to reach our webhook at a public URL."""
        return bool(self.settings.public_base_url)

    def owner_number(self) -> str:
        if not self.settings.my_phone_number:
            raise PhoneError("MY_PHONE_NUMBER isn't set in .env, so I don't know your number.")
        return normalize_number(self.settings.my_phone_number)

    # --- calls ----------------------------------------------------------------
    def call(
        self,
        number: str,
        message: str,
        *,
        contact_name: str = "",
        conversation: bool = False,
        with_owner: bool = False,
    ) -> int:
        """Place a call and return our phone_calls row id.

        One-way calls speak ``message`` and hang up. Conversational calls speak it
        and then chat back and forth through the /twilio/* webhooks.
        """
        number = normalize_number(number)
        call_id = self.db.execute(
            "INSERT INTO phone_calls (direction, number, contact_name, purpose, with_owner, created_at) "
            "VALUES ('outbound', ?, ?, ?, ?, ?)",
            (number, contact_name, message, int(with_owner), utcnow()),
        )
        params: dict[str, Any] = {"to": number, "from_": self.settings.twilio_phone_number}
        base = self.settings.public_base_url
        if conversation and base:
            params["url"] = f"{base}/twilio/voice?call_id={call_id}"
        else:
            vr = VoiceResponse()
            vr.pause(length=1)
            say(vr, message)
            vr.pause(length=1)
            say(vr, "Once again: " + message)
            params["twiml"] = str(vr)
        if base:
            params["status_callback"] = f"{base}/twilio/status?call_id={call_id}"
        call = self.client.calls.create(**params)
        self.db.execute("UPDATE phone_calls SET call_sid = ? WHERE id = ?", (call.sid, call_id))
        return call_id

    def call_owner(self, message: str, conversation: bool = False) -> int:
        return self.call(
            self.owner_number(), message, contact_name="you", conversation=conversation, with_owner=True
        )

    # --- texts ----------------------------------------------------------------
    def text(self, number: str, body: str) -> str:
        msg = self.client.messages.create(
            to=normalize_number(number), from_=self.settings.twilio_phone_number, body=body
        )
        return msg.sid

    def text_owner(self, body: str) -> str:
        return self.text(self.owner_number(), body)
