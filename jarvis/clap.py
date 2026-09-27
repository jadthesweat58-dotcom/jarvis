"""Clap twice to open Jarvis.

Runs quietly on your own computer, listening to the microphone for a double
clap. Nothing is recorded or sent anywhere: each tiny slice of sound is checked
for the sharp spike of a clap and then thrown away. On a double clap it opens
the Jarvis dashboard in your browser and greets you out loud.

    python -m jarvis.clap              # listen and open Jarvis on a double clap
    python -m jarvis.clap --test       # just print when it hears claps (for tuning)
    python -m jarvis.clap --levels     # show live sound levels, to pick a sensitivity

Settings (in .env): JARVIS_URL (default http://localhost:8000),
CLAP_SENSITIVITY (1-10, default 5; higher hears quieter claps).
"""

from __future__ import annotations

import argparse
import os
import platform
import shutil
import subprocess
import sys
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


def say(text: str) -> None:
    """Speak with the computer's own voice (British "Daniel" on a Mac)."""
    system = platform.system()
    try:
        if system == "Darwin":
            subprocess.Popen(["say", "-v", "Daniel", text])
        elif system == "Windows":
            ps = ("Add-Type -AssemblyName System.Speech; "
                  "(New-Object System.Speech.Synthesis.SpeechSynthesizer).Speak($args[0])")
            subprocess.Popen(["powershell", "-NoProfile", "-Command", ps, text],
                             creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))
        elif shutil.which("espeak"):
            subprocess.Popen(["espeak", text])
    except OSError:
        pass  # no voice available; opening the dashboard still works


def open_jarvis(url: str, name: str) -> None:
    webbrowser.open(url)
    say(greeting(name))


def run(test: bool = False, levels: bool = False) -> None:
    try:
        import sounddevice as sd
    except (ImportError, OSError):
        sys.exit("Clap-to-open needs the microphone packages. Run:\n"
                 "    pip install -r requirements-local.txt\n"
                 "(On Linux, also install PortAudio: sudo apt install libportaudio2)")
    from jarvis.config import settings

    url = os.environ.get("JARVIS_URL", "http://localhost:8000").strip()
    sensitivity = int(os.environ.get("CLAP_SENSITIVITY", "5") or 5)
    detector = ClapDetector(sensitivity)
    print(f"Listening for a double clap (sensitivity {sensitivity}). Press Ctrl+C to stop.")

    def on_audio(indata, frames, time_info, status):
        block = indata[:, 0]
        if levels:
            bar = "#" * int(min(float(np.max(np.abs(block))), 1.0) * 50)
            print(f"\r{bar:<50}", end="", flush=True)
        if detector.feed(block, time.monotonic()):
            if test:
                print("\nClap clap! (test mode: not opening Jarvis)")
            else:
                print("\nClap clap! Opening Jarvis…")
                open_jarvis(url, settings.my_name)

    try:
        with sd.InputStream(channels=1, samplerate=SAMPLE_RATE, blocksize=BLOCK, callback=on_audio):
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
