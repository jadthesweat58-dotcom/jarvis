import numpy as np
import pytest

from jarvis.clap import BLOCK, SAMPLE_RATE, ClapDetector, greeting

rng = np.random.default_rng(7)


def silence(seconds, level=0.004):
    return rng.normal(0, level, int(SAMPLE_RATE * seconds)).astype(np.float32)


def clap(level=0.8):
    """A clap: a sharp burst that dies away within ~60 ms."""
    n = int(SAMPLE_RATE * 0.06)
    return (rng.normal(0, level / 2.5, n) * np.exp(-np.linspace(0, 8, n))).clip(-1, 1).astype(np.float32)


def speech(seconds, level=0.35):
    """Sustained voice-like sound: a buzzing tone that stays loud."""
    t = np.arange(int(SAMPLE_RATE * seconds)) / SAMPLE_RATE
    wave = np.sin(2 * np.pi * 180 * t) * (0.6 + 0.4 * np.sin(2 * np.pi * 4 * t))
    return (level * wave).astype(np.float32)


def run(audio, sensitivity=5):
    det = ClapDetector(sensitivity)
    hits = []
    for i in range(0, len(audio) - BLOCK + 1, BLOCK):
        t = i / SAMPLE_RATE
        if det.feed(audio[i:i + BLOCK], t):
            hits.append(round(t, 2))
    return hits


def test_double_clap_triggers_once():
    audio = np.concatenate([silence(1.0), clap(), silence(0.3), clap(), silence(1.0)])
    assert len(run(audio)) == 1


def test_single_clap_does_nothing():
    assert run(np.concatenate([silence(1.0), clap(), silence(2.0)])) == []


def test_claps_too_far_apart_do_nothing():
    audio = np.concatenate([silence(1.0), clap(), silence(1.5), clap(), silence(1.0)])
    assert run(audio) == []


def test_talking_and_music_do_nothing():
    audio = np.concatenate([silence(1.0), speech(1.5), silence(0.3), speech(1.0), silence(1.0)])
    assert run(audio) == []


def test_soft_claps_need_higher_sensitivity():
    audio = np.concatenate([silence(1.0), clap(0.35), silence(0.3), clap(0.35), silence(1.0)])
    assert run(audio, sensitivity=2) == []
    assert len(run(audio, sensitivity=9)) == 1


def test_three_claps_trigger_only_once():
    audio = np.concatenate([silence(1.0), clap(), silence(0.3), clap(), silence(0.3), clap(), silence(1.0)])
    assert len(run(audio)) == 1


def test_works_in_a_noisier_room():
    audio = np.concatenate([silence(1.0, 0.03), clap(), silence(0.35, 0.03), clap(), silence(1.0, 0.03)])
    assert len(run(audio)) == 1


@pytest.mark.parametrize("hour,part", [(8, "morning"), (14, "afternoon"), (21, "evening")])
def test_greeting(monkeypatch, hour, part):
    import jarvis.clap as clap_mod

    class FakeDateTime:
        @staticmethod
        def now():
            from datetime import datetime
            return datetime(2026, 9, 27, hour)

    monkeypatch.setattr(clap_mod, "datetime", FakeDateTime)
    assert greeting("Jad") == f"Good {part}, Jad. Jarvis online."


def test_listener_opens_jarvis_on_double_clap(monkeypatch):
    """The whole loop, with a fake microphone that plays two claps."""
    import sys
    import types

    import jarvis.clap as clap_mod

    audio = np.concatenate([silence(1.0), clap(), silence(0.3), clap(), silence(0.5)])

    class FakeStream:
        def __init__(self, channels, samplerate, blocksize, callback):
            self.callback, self.blocksize = callback, blocksize

        def __enter__(self):
            for i in range(0, len(audio) - self.blocksize + 1, self.blocksize):
                self.callback(audio[i:i + self.blocksize].reshape(-1, 1), self.blocksize, None, None)
            return self

        def __exit__(self, *exc):
            return False

    monkeypatch.setitem(sys.modules, "sounddevice", types.SimpleNamespace(InputStream=FakeStream))
    clock = iter(np.arange(0, 10, BLOCK / SAMPLE_RATE))
    monkeypatch.setattr(clap_mod.time, "monotonic", lambda: next(clock))
    monkeypatch.setattr(clap_mod.time, "sleep", lambda s: (_ for _ in ()).throw(KeyboardInterrupt))
    opened, spoken = [], []
    monkeypatch.setattr(clap_mod.webbrowser, "open", opened.append)
    monkeypatch.setattr(clap_mod, "say", spoken.append)
    monkeypatch.setenv("JARVIS_URL", "https://jarvis-test.onrender.com")

    clap_mod.run()
    assert opened == ["https://jarvis-test.onrender.com"]
    assert len(spoken) == 1 and "Jarvis online" in spoken[0]
