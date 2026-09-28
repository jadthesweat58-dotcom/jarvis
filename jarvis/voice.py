"""Jarvis's voice: turns replies into speech with ElevenLabs.

The API key stays on the server; the browser asks /api/tts for the audio.
"""

from __future__ import annotations

import threading
from collections import OrderedDict
from typing import TYPE_CHECKING, Any, Callable

import httpx

if TYPE_CHECKING:
    from jarvis.config import Settings

API = "https://api.elevenlabs.io/v1/text-to-speech"
MAX_CHARS = 1000      # longer replies are cut, to protect the monthly character quota
CACHE_SIZE = 64       # remember recent phrases ("Yes?", greetings) instead of paying twice


class VoiceError(Exception):
    pass


class ElevenLabsVoice:
    def __init__(self, settings: "Settings", client: Any = None,
                 on_usage: Callable[[int], None] | None = None):
        self.settings = settings
        self.on_usage = on_usage  # told how many characters each (paid) request used
        self._http = client or httpx.Client(timeout=30)
        self._cache: OrderedDict[str, bytes] = OrderedDict()
        self._lock = threading.Lock()

    @property
    def enabled(self) -> bool:
        return self.settings.tts_enabled

    def speak(self, text: str) -> bytes:
        """MP3 audio for the text."""
        text = " ".join(text.split())[:MAX_CHARS]
        if not text:
            raise VoiceError("Nothing to say.")
        with self._lock:
            if text in self._cache:
                self._cache.move_to_end(text)
                return self._cache[text]
        resp = self._http.post(
            f"{API}/{self.settings.elevenlabs_voice_id}",
            params={"output_format": "mp3_44100_128"},
            headers={"xi-api-key": self.settings.elevenlabs_api_key, "Accept": "audio/mpeg"},
            json={"text": text, "model_id": self.settings.elevenlabs_model},
        )
        if resp.status_code != 200:
            raise VoiceError(self._explain(resp))
        audio = resp.content
        if self.on_usage:
            try:
                self.on_usage(len(text))
            except Exception:
                pass  # the meter must never stop Jarvis talking
        with self._lock:
            self._cache[text] = audio
            if len(self._cache) > CACHE_SIZE:
                self._cache.popitem(last=False)
        return audio

    @staticmethod
    def _explain(resp: httpx.Response) -> str:
        try:
            detail = resp.json().get("detail")
        except ValueError:
            detail = None
        message = detail.get("message") if isinstance(detail, dict) else detail
        status = detail.get("status", "") if isinstance(detail, dict) else ""
        if "quota" in str(status) or "quota" in str(message).lower():
            return "ElevenLabs quota used up for this month."
        if resp.status_code == 401:
            return "ElevenLabs rejected the API key. Check ELEVENLABS_API_KEY."
        if resp.status_code == 404:
            return "ElevenLabs couldn't find that voice. Check ELEVENLABS_VOICE_ID."
        return f"ElevenLabs error {resp.status_code}: {message or resp.text[:200]}"
