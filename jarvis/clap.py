"""Clap twice to open Jarvis.

Runs quietly on your own computer, listening to the microphone for a double
clap. Nothing is recorded or sent anywhere: each tiny slice of sound is checked
for the sharp spike of a clap and then thrown away. On a double clap it opens
the Jarvis dashboard in your browser and greets you out loud.

    python -m jarvis.clap              # listen and open Jarvis on a double clap
    python -m jarvis.clap --test       # just print when it hears claps (for tuning)
    python -m jarvis.clap --levels     # show live sound levels, to pick a sensitivity

Settings (in .env): JARVIS_URL (default http://localhost:8000),
CLAP_SENSITIVITY (1-10, default 5; higher hears quieter claps), CLAP_BRIEFING
(on/off, default on: read today's briefing after the greeting; for a cloud
JARVIS_URL also set JARVIS_ACCESS_TOKEN).
"""

from __future__ import annotations

import argparse
import os
import platform
import shutil
import subprocess
import sys
import threading
import time
import webbrowser
from datetime import datetime

import numpy as np

SAMPLE_RATE = 16000
BLOCK = 256                  # 16 ms of audio per check


class ClapDetector:
    """Finds two claps in a row in a stream of audio blocks.

    A clap is a sudden, loud, short spike: much louder than the room's usual
    background, rising sharply from a quiet moment and dying away within about
    a tenth of a second. Speech and music are sustained, so they don't count.
    """

    MIN_GAP = 0.12           # seconds between the two claps
    MAX_GAP = 0.8
    MAX_CLAP_LENGTH = 0.12   # a clap is over within ~120 ms
    COOLDOWN = 2.0           # ignore claps right after a trigger

    def __init__(self, sensitivity: int = 5, sample_rate: int = SAMPLE_RATE):
        s = min(max(int(sensitivity), 1), 10)
        # Sensitivity 1 needs a very loud clap; 10 hears a soft one.
        self.min_peak = 0.55 - s * 0.045            # absolute peak level (0-1)
        self.ratio = 22 - s                         # how far the peak must rise above the background
        self.sample_rate = sample_rate
        self.floor = 0.01                           # running background loudness
        self.prev_rms = 0.0
        self.in_clap_since: float | None = None
        self.last_clap: float | None = None
        self.cooldown_until = 0.0

    def feed(self, block: np.ndarray, now: float) -> bool:
        """Process one block (mono floats, -1..1). True when a double clap completes."""
        block = np.asarray(block, dtype=np.float32).reshape(-1)
        rms = float(np.sqrt(np.mean(block * block))) if block.size else 0.0
        peak = float(np.max(np.abs(block))) if block.size else 0.0
        triggered = False

        loud = peak >= self.min_peak and peak >= self.floor * self.ratio
        if self.in_clap_since is None:
            # A clap starts suddenly, out of relative quiet.
            if loud and rms >= max(self.prev_rms, self.floor) * 3:
                self.in_clap_since = now
        elif rms < max(self.floor * 3, self.min_peak * 0.12):
            # The sound died away: was it short enough to be a clap?
            if now - self.in_clap_since <= self.MAX_CLAP_LENGTH + BLOCK / self.sample_rate:
                triggered = self._clap(self.in_clap_since)
            self.in_clap_since = None
        elif now - self.in_clap_since > self.MAX_CLAP_LENGTH * 3:
            self.in_clap_since = None               # a long noise, not a clap

        if self.in_clap_since is None and not loud:
            # Learn the room's background level slowly (never from the claps themselves).
            self.floor = max(0.002, self.floor * 0.98 + rms * 0.02)
        self.prev_rms = rms
        return triggered

    def _clap(self, when: float) -> bool:
        if when < self.cooldown_until:
            return False
        if self.last_clap is not None and self.MIN_GAP <= when - self.last_clap <= self.MAX_GAP:
            self.last_clap = None
            self.cooldown_until = when + self.COOLDOWN
            return True
        self.last_clap = when
        return False


def greeting(name: str) -> str:
    hour = datetime.now().hour
    part = "morning" if hour < 12 else "afternoon" if hour < 18 else "evening"
    return f"Good {part}, {name}. Jarvis online."


def say(text: str, wait: bool = False) -> None:
    """Speak with the computer's own voice (British "Daniel" on a Mac)."""
    system = platform.system()
    try:
        if system == "Darwin":
            proc = subprocess.Popen(["say", "-v", "Daniel", text])
        elif system == "Windows":
            ps = ("Add-Type -AssemblyName System.Speech; "
                  "(New-Object System.Speech.Synthesis.SpeechSynthesizer).Speak($args[0])")
            proc = subprocess.Popen(["powershell", "-NoProfile", "-Command", ps, text],
                                    creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))
        elif shutil.which("espeak"):
            proc = subprocess.Popen(["espeak", text])
        else:
            return
        if wait:
            proc.wait()
    except OSError:
        pass  # no voice available; opening the dashboard still works


def fetch_briefing(url: str, token: str = "") -> str | None:
    """Today's briefing from the Jarvis server (local or cloud), or None."""
    import httpx

    headers = {"Authorization": f"Bearer {token}"} if token else {}
    try:
        resp = httpx.post(url.rstrip("/") + "/api/briefing", json={}, headers=headers, timeout=90)
        if resp.status_code == 200:
            return (resp.json().get("text") or "").strip() or None
    except Exception:
        pass  # server asleep or unreachable: the greeting alone will do
    return None


def open_jarvis(url: str, name: str, briefing: bool = True, token: str = "") -> None:
    webbrowser.open(url)
    say(greeting(name), wait=briefing)
    if briefing:
        text = fetch_briefing(url, token)
        if text:
            say(text)


class ClapListener:
    """Listens to the microphone in the background and calls ``on_double_clap``.
    Used by ``run`` below and by the menu-bar app (jarvis/tray.py)."""

    def __init__(self, on_double_clap, sensitivity: int = 5, on_level=None):
        import sounddevice as sd  # ImportError / OSError if the microphone packages are missing

        self.detector = ClapDetector(sensitivity)
        self.on_double_clap = on_double_clap
        self.on_level = on_level
        self._sd = sd
        self._stream = None

    @property
    def running(self) -> bool:
        return self._stream is not None

    def _audio(self, indata, frames, time_info, status) -> None:
        block = indata[:, 0]
        if self.on_level:
            self.on_level(block)
        if self.detector.feed(block, time.monotonic()):
            # Off the audio thread: opening Jarvis and fetching the briefing take a moment.
            threading.Thread(target=self.on_double_clap, daemon=True).start()

    def start(self) -> None:
        if self._stream is None:
            stream = self._sd.InputStream(channels=1, samplerate=SAMPLE_RATE, blocksize=BLOCK, callback=self._audio)
            stream.start()
            self._stream = stream

    def stop(self) -> None:
        if self._stream is not None:
            self._stream.stop()
            self._stream.close()
            self._stream = None


def settings_from_env() -> tuple[str, int, bool]:
    url = os.environ.get("JARVIS_URL", "http://localhost:8000").strip()
    sensitivity = int(os.environ.get("CLAP_SENSITIVITY", "5") or 5)
    briefing = os.environ.get("CLAP_BRIEFING", "on").strip().lower() not in ("off", "0", "no", "false")
    return url, sensitivity, briefing


def run(test: bool = False, levels: bool = False) -> None:
    try:
        import sounddevice  # noqa: F401
    except (ImportError, OSError):
        sys.exit("Clap-to-open needs the microphone packages. Run:\n"
                 "    pip install -r requirements-local.txt\n"
                 "(On Linux, also install PortAudio: sudo apt install libportaudio2)")
    from jarvis.config import settings

    url, sensitivity, briefing = settings_from_env()

    def clapped() -> None:
        if test:
            print("\nClap clap! (test mode: not opening Jarvis)")
        else:
            print("\nClap clap! Opening Jarvis…")
            open_jarvis(url, settings.my_name, briefing, settings.access_token)

    def show_level(block) -> None:
        bar = "#" * int(min(float(np.max(np.abs(block))), 1.0) * 50)
        print(f"\r{bar:<50}", end="", flush=True)

    print(f"Listening for a double clap (sensitivity {sensitivity}). Press Ctrl+C to stop.")
    try:
        listener = ClapListener(clapped, sensitivity, on_level=show_level if levels else None)
        listener.start()
        while True:
            time.sleep(0.5)
    except KeyboardInterrupt:
        print("\nStopped listening.")
    except Exception as exc:  # no microphone, permission denied, …
        sys.exit(f"Couldn't use the microphone: {exc}\n"
                 "On a Mac, allow microphone access for Terminal in System Settings > Privacy & Security.")


def main() -> None:
    parser = argparse.ArgumentParser(description="Clap twice to open Jarvis.")
    parser.add_argument("--test", action="store_true", help="print claps instead of opening Jarvis")
    parser.add_argument("--levels", action="store_true", help="show live sound levels")
    args = parser.parse_args()
    run(test=args.test, levels=args.levels)


if __name__ == "__main__":
    main()
