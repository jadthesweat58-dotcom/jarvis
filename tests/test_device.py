"""Computer controls, with the operating system faked (no real commands run)."""

import subprocess
from types import SimpleNamespace

import pytest

from jarvis.tools import REGISTRY, ToolError, available_tools, load_all
from jarvis.tools import device


@pytest.fixture
def mac(monkeypatch):
    calls = []
    answers = {}

    def fake_run(args, capture_output=True, text=True, timeout=None):
        calls.append(args)
        script = args[-1] if args[0] == "osascript" else " ".join(args)
        for key, value in answers.items():
            if key in script:
                return SimpleNamespace(returncode=value[0], stdout=value[1], stderr=value[2] if len(value) > 2 else "")
        return SimpleNamespace(returncode=0, stdout="", stderr="")

    monkeypatch.setattr(device.subprocess, "run", fake_run)
    monkeypatch.setattr(device.platform, "system", lambda: "Darwin")
    monkeypatch.setattr(device.time, "sleep", lambda s: None)
    return SimpleNamespace(calls=calls, answers=answers)


def run(ctx, tool_name, **args):
    load_all()
    return REGISTRY[tool_name].handler(ctx, args)


def scripts(mac):
    return [c[-1] for c in mac.calls if c[0] == "osascript"]


def test_tools_are_local_only(ctx):
    names = {t.name for t in available_tools(ctx.settings)}
    assert not names & {"media_control", "set_volume", "send_whatsapp", "lock_screen"}
    ctx.settings.mode = "local"
    assert {"media_control", "set_volume", "set_brightness", "send_whatsapp", "lock_screen", "empty_trash"} <= \
        {t.name for t in available_tools(ctx.settings)}
    assert REGISTRY["empty_trash"].needs_approval and REGISTRY["send_whatsapp"].needs_approval
    assert REGISTRY["run_shortcut"].needs_approval


def test_music(ctx, mac):
    mac.answers["every process"] = (0, "Finder, Spotify, Safari")
    mac.answers["player state"] = (0, "playing")
    mac.answers["current track"] = (0, "Blinding Lights by The Weeknd")
    assert run(ctx, "media_control", action="next") == "Spotify: next."
    assert 'tell application "Spotify" to next track' in scripts(mac)
    assert run(ctx, "media_control", action="now_playing") == "Playing Blinding Lights by The Weeknd on Spotify."
    mac.answers["every process"] = (0, "Finder, Safari")
    assert run(ctx, "media_control", action="pause") == "No music app is open."


def test_volume_and_brightness(ctx, mac):
    mac.answers["output volume of"] = (0, "40")
    assert run(ctx, "set_volume", change="up") == "Volume set to 50%."
    assert run(ctx, "set_volume", level=250) == "Volume set to 100%."
    assert "set volume output volume 100 without output muted" in scripts(mac)
    assert run(ctx, "set_volume", change="mute") == "Muted."
    run(ctx, "set_brightness", level=50)
    assert "repeat 16 times\nkey code 145" in scripts(mac)[-1] and "repeat 8 times\nkey code 144" in scripts(mac)[-1]
    with pytest.raises(ToolError):
        run(ctx, "set_volume")


def test_permission_errors_explain_the_fix(ctx, mac):
    mac.answers["key code"] = (1, "", "System Events got an error: osascript is not allowed assistive access. (-1719)")
    with pytest.raises(ToolError, match="Accessibility"):
        run(ctx, "set_brightness", change="up")


def test_focus_needs_a_shortcut(ctx, mac, monkeypatch):
    monkeypatch.setattr(device.shutil, "which", lambda name: "/usr/bin/shortcuts" if name == "shortcuts" else None)
    mac.answers["shortcuts list"] = (0, "Morning\nJarvis Focus On\n")
    assert run(ctx, "do_not_disturb", on=True) == "Do Not Disturb is on."
    assert ["shortcuts", "run", "Jarvis Focus On"] in mac.calls
    with pytest.raises(ToolError, match='Shortcut called "Jarvis Focus Off"'):
        run(ctx, "do_not_disturb", on=False)
    with pytest.raises(ToolError, match="Did you mean: Morning"):
        run(ctx, "run_shortcut", name="morn")


def test_whatsapp_sends_to_a_contact(ctx, mac):
    load_all()
    REGISTRY["add_contact"].handler(ctx, {"name": "Ahmed", "phone": "+971501234567"})
    args = REGISTRY["send_whatsapp"].prepare(ctx, {"to": "ahmed", "message": "Running 10 min late & sorry!"})
    assert args["number"] == "+971501234567"
    assert REGISTRY["send_whatsapp"].describe(ctx, args) == 'WhatsApp Ahmed (+971501234567): "Running 10 min late & sorry!"'
    assert run(ctx, "send_whatsapp", **args) == "Sent your WhatsApp message to Ahmed."
    assert ["open", "whatsapp://send?phone=971501234567&text=Running%2010%20min%20late%20%26%20sorry%21"] in mac.calls
    assert "key code 36" in scripts(mac)[-1]


def test_whatsapp_without_accessibility_leaves_it_typed(ctx, mac):
    mac.answers["key code 36"] = (1, "", "not allowed to send keystrokes (1002)")
    out = run(ctx, "send_whatsapp", to="+971501234567", number="+971501234567", message="hi")
    assert "press Enter to send it" in out and "Accessibility" in out


def test_windows_media_keys(ctx, monkeypatch):
    sent = []
    monkeypatch.setattr(device.platform, "system", lambda: "Windows")
    monkeypatch.setattr(device.subprocess, "run",
                        lambda args, **kw: sent.append(args) or SimpleNamespace(returncode=0, stdout="", stderr=""))
    assert run(ctx, "media_control", action="play_pause") == "Pressed play/pause."
    assert "[char]179" in sent[-1][-1]
    run(ctx, "set_volume", level=30)
    assert "1..50" in sent[-2][-1] and "1..15" in sent[-1][-1]
