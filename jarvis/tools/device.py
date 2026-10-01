"""Controlling the computer Jarvis runs on: music, volume, brightness, Focus,
locking the screen, emptying the trash, Shortcuts, and WhatsApp messages.

Only available when JARVIS_MODE=local. Works best on a Mac (AppleScript);
Windows is supported where it has built-in ways to do the same thing.
Every command here is built from fixed text plus validated numbers, never from
anything the AI writes, so nothing unexpected can run.
"""

from __future__ import annotations

import platform
import shutil
import subprocess
import time
import webbrowser
from urllib.parse import quote

from jarvis.tools import Context, ToolError, tool

PLAYERS = ("Spotify", "Music")
# Windows virtual-key codes for the media and volume keys.
VK = {"play_pause": 179, "next": 176, "previous": 177, "volume_up": 175, "volume_down": 174, "mute": 173}
ACCESSIBILITY_HELP = ("Allow it once: System Settings > Privacy & Security > Accessibility > turn on Terminal "
                      "(or the app running Jarvis).")


def system() -> str:
    return platform.system()


def run(args: list[str], timeout: float = 15) -> subprocess.CompletedProcess:
    try:
        return subprocess.run(args, capture_output=True, text=True, timeout=timeout)
    except (OSError, subprocess.TimeoutExpired) as exc:
        raise ToolError(f"That didn't work: {exc}") from exc


def osascript(script: str) -> str:
    proc = run(["osascript", "-e", script])
    if proc.returncode != 0:
        err = (proc.stderr or "").strip()
        if "not allowed" in err.lower() or "1002" in err or "-1743" in err or "assistive" in err.lower():
            raise ToolError(f"macOS blocked Jarvis from doing that. {ACCESSIBILITY_HELP}")
        raise ToolError(f"That didn't work: {err[:200] or 'unknown error'}")
    return (proc.stdout or "").strip()


def powershell(script: str) -> str:
    proc = run(["powershell", "-NoProfile", "-NonInteractive", "-Command", script])
    if proc.returncode != 0:
        raise ToolError(f"That didn't work: {(proc.stderr or '').strip()[:200]}")
    return (proc.stdout or "").strip()


def press_windows_key(code: int, times: int = 1) -> None:
    powershell(f"$w = New-Object -ComObject WScript.Shell; 1..{int(times)} | ForEach-Object {{ $w.SendKeys([char]{int(code)}) }}")


def unsupported() -> ToolError:
    return ToolError(f"That isn't supported on {system()} yet.")


# ------------------------------------------------------------------ music
def running_player() -> str | None:
    names = osascript('tell application "System Events" to get name of every process whose background only is false')
    open_apps = {n.strip() for n in names.split(",")}
    return next((p for p in PLAYERS if p in open_apps), None)


@tool(
    "media_control",
    "Control music on the user's computer (Spotify or Apple Music): play, pause, next, previous, "
    "or say what's playing.",
    {"action": {"type": "string", "enum": ["play", "pause", "play_pause", "next", "previous", "now_playing"]}},
    ["action"],
    local_only=True,
)
def media_control(ctx: Context, args: dict) -> str:
    action = args.get("action")
    if action not in ("play", "pause", "play_pause", "next", "previous", "now_playing"):
        raise ToolError("Unknown music action.")
    os_name = system()
    if os_name == "Darwin":
        player = running_player()
        if not player:
            if action in ("play", "play_pause"):
                player = "Spotify" if shutil.which("spotify") or _mac_app_exists("Spotify") else "Music"
            else:
                return "No music app is open."
        if action == "now_playing":
            state = osascript(f'tell application "{player}" to get player state as string')
            if state != "playing":
                return f"{player} is {state}."
            track = osascript(f'tell application "{player}" to get (name of current track) & " by " & (artist of current track)')
            return f"Playing {track} on {player}."
        command = {"play": "play", "pause": "pause", "play_pause": "playpause",
                   "next": "next track", "previous": "previous track"}[action]
        osascript(f'tell application "{player}" to {command}')
        return f"{player}: {action.replace('_', '/')}."
    if os_name == "Windows":
        if action == "now_playing":
            raise ToolError("I can't see what's playing on Windows yet.")
        press_windows_key(VK["play_pause" if action in ("play", "pause", "play_pause") else action])
        return f"Pressed {action.replace('_', '/')}."
    if shutil.which("playerctl"):
        cmd = {"play": "play", "pause": "pause", "play_pause": "play-pause", "next": "next",
               "previous": "previous", "now_playing": "metadata"}[action]
        out = run(["playerctl", cmd] + (["--format", "{{title}} by {{artist}}"] if action == "now_playing" else []))
        return out.stdout.strip() or "Done."
    raise unsupported()


def _mac_app_exists(name: str) -> bool:
    from pathlib import Path

    return any(Path(base, f"{name}.app").exists() for base in ("/Applications", str(Path.home() / "Applications")))


# ------------------------------------------------------------------ volume + brightness
@tool(
    "set_volume",
    "Change the computer's sound volume: a level from 0 to 100, a step up or down, or mute / unmute.",
    {
        "level": {"type": "integer", "description": "0-100"},
        "change": {"type": "string", "enum": ["up", "down", "mute", "unmute"]},
    },
    local_only=True,
)
def set_volume(ctx: Context, args: dict) -> str:
    level, change = args.get("level"), args.get("change")
    if level is None and not change:
        raise ToolError("Give a level (0-100) or a change (up, down, mute, unmute).")
    os_name = system()
    if os_name == "Darwin":
        if change == "mute":
            osascript("set volume with output muted")
            return "Muted."
        if change == "unmute":
            osascript("set volume without output muted")
            return "Unmuted."
        if level is None:
            current = int(osascript("output volume of (get volume settings)") or 50)
            level = current + (10 if change == "up" else -10)
        level = min(max(int(level), 0), 100)
        osascript(f"set volume output volume {level} without output muted")
        return f"Volume set to {level}%."
    if os_name == "Windows":
        if change in ("mute", "unmute"):
            press_windows_key(VK["mute"])
            return "Toggled mute."
        if level is None:
            press_windows_key(VK["volume_up" if change == "up" else "volume_down"], 5)
            return f"Volume {change}."
        level = min(max(int(level), 0), 100)
        press_windows_key(VK["volume_down"], 50)  # each press is 2%: go to 0, then up to the level
        press_windows_key(VK["volume_up"], round(level / 2))
        return f"Volume set to about {level}%."
    if shutil.which("amixer"):
        value = {"mute": "mute", "unmute": "unmute", "up": "10%+", "down": "10%-"}.get(change) or f"{int(level)}%"
        run(["amixer", "-q", "set", "Master", value])
        return "Done."
    raise unsupported()


@tool(
    "set_brightness",
    "Change the screen brightness: a level from 0 to 100, or a step up or down.",
    {
        "level": {"type": "integer", "description": "0-100"},
        "change": {"type": "string", "enum": ["up", "down"]},
    },
    local_only=True,
)
def set_brightness(ctx: Context, args: dict) -> str:
    level, change = args.get("level"), args.get("change")
    if level is None and change not in ("up", "down"):
        raise ToolError("Give a level (0-100) or a change (up or down).")
    os_name = system()
    if os_name == "Darwin":
        # The brightness keys (key codes 144 up, 145 down); 16 steps from dark to full.
        if level is None:
            presses = [(144 if change == "up" else 145, 2)]
        else:
            presses = [(145, 16), (144, round(min(max(int(level), 0), 100) / 6.25))]
        script = "\n".join(f"repeat {n} times\nkey code {code}\nend repeat" for code, n in presses if n)
        osascript(f'tell application "System Events"\n{script}\nend tell')
        return f"Brightness {'set to about ' + str(level) + '%' if level is not None else change}."
    if os_name == "Windows":
        if level is None:
            current = int(powershell("(Get-CimInstance -Namespace root/WMI -ClassName WmiMonitorBrightness).CurrentBrightness") or 50)
            level = current + (15 if change == "up" else -15)
        level = min(max(int(level), 0), 100)
        powershell(f"(Get-CimInstance -Namespace root/WMI -ClassName WmiMonitorBrightnessMethods)"
                   f" | Invoke-CimMethod -MethodName WmiSetBrightness -Arguments @{{Timeout=1; Brightness={level}}}")
        return f"Brightness set to {level}%."
    raise unsupported()


# ------------------------------------------------------------------ Focus, lock, trash, Shortcuts
FOCUS_SHORTCUTS = {True: "Jarvis Focus On", False: "Jarvis Focus Off"}


@tool(
    "do_not_disturb",
    "Turn Do Not Disturb (Focus) on or off on the user's Mac.",
    {"on": {"type": "boolean"}},
    ["on"],
    local_only=True,
)
def do_not_disturb(ctx: Context, args: dict) -> str:
    if system() != "Darwin":
        raise unsupported()
    on = bool(args.get("on"))
    name = FOCUS_SHORTCUTS[on]
    if name not in shortcut_names():
        raise ToolError(f"First make a Shortcut called \"{name}\" in the Shortcuts app with the action "
                        f"\"Set Focus\" (Do Not Disturb, turn {'On' if on else 'Off'}). Then ask me again.")
    proc = run(["shortcuts", "run", name], timeout=30)
    if proc.returncode != 0:
        raise ToolError(f"The Shortcut didn't run: {(proc.stderr or '').strip()[:200]}")
    return f"Do Not Disturb is {'on' if on else 'off'}."


def shortcut_names() -> list[str]:
    if not shutil.which("shortcuts"):
        return []
    return [line.strip() for line in run(["shortcuts", "list"]).stdout.splitlines() if line.strip()]


@tool(
    "run_shortcut",
    "Run one of the user's Shortcuts (Mac Shortcuts app) by its exact name, e.g. a home or music "
    "shortcut they made. The user approves it.",
    {"name": {"type": "string"}},
    ["name"],
    local_only=True,
    needs_approval=True,
    summarize=lambda ctx, a: f"Run the Shortcut \"{a.get('name', '')}\"",
)
def run_shortcut(ctx: Context, args: dict) -> str:
    if system() != "Darwin":
        raise unsupported()
    name = str(args.get("name", "")).strip()
    names = shortcut_names()
    if name not in names:
        close = [n for n in names if name.lower() in n.lower()][:5]
        raise ToolError(f"No Shortcut called \"{name}\"." + (f" Did you mean: {', '.join(close)}?" if close else ""))
    proc = run(["shortcuts", "run", name], timeout=120)
    if proc.returncode != 0:
        raise ToolError(f"The Shortcut didn't run: {(proc.stderr or '').strip()[:200]}")
    return f"Ran \"{name}\"." + (f" Output: {proc.stdout.strip()[:500]}" if proc.stdout.strip() else "")


@tool("lock_screen", "Lock the computer's screen right away.", local_only=True)
def lock_screen(ctx: Context, args: dict) -> str:
    os_name = system()
    if os_name == "Darwin":
        try:  # the Lock Screen shortcut (Ctrl+Cmd+Q)
            osascript('tell application "System Events" to keystroke "q" using {control down, command down}')
        except ToolError:
            run(["pmset", "displaysleepnow"])  # screen off; locks if a password is required after sleep
        return "Locked."
    if os_name == "Windows":
        run(["rundll32.exe", "user32.dll,LockWorkStation"])
        return "Locked."
    if shutil.which("loginctl"):
        run(["loginctl", "lock-session"])
        return "Locked."
    raise unsupported()


@tool(
    "empty_trash",
    "Empty the computer's Trash / Recycle Bin. This deletes those files for good, so the user approves it.",
    local_only=True,
    needs_approval=True,
    summarize=lambda ctx, a: "Empty the Trash (files there are deleted for good)",
)
def empty_trash(ctx: Context, args: dict) -> str:
    os_name = system()
    if os_name == "Darwin":
        osascript('tell application "Finder" to empty trash')
        return "Trash emptied."
    if os_name == "Windows":
        powershell("Clear-RecycleBin -Force -ErrorAction SilentlyContinue")
        return "Recycle Bin emptied."
    raise unsupported()


# ------------------------------------------------------------------ WhatsApp
def _whatsapp_running() -> bool:
    try:
        return osascript('tell application "System Events" to (name of processes) contains "WhatsApp"') == "true"
    except ToolError:
        return False


def _freeze_whatsapp(ctx: Context, args: dict) -> dict:
    from jarvis.tools.calls import find_contact

    name, number = find_contact(ctx, str(args.get("to", "")))
    return {**args, "to": name, "number": number}


@tool(
    "send_whatsapp",
    "Send a WhatsApp message from the user's computer (WhatsApp desktop app, or WhatsApp Web) to a "
    "saved contact or a number in international format. The user approves every message.",
    {
        "to": {"type": "string", "description": "Contact name, or a number like +971501234567"},
        "message": {"type": "string"},
    },
    ["to", "message"],
    local_only=True,
    needs_approval=True,
    prepare=_freeze_whatsapp,
    summarize=lambda ctx, a: f"WhatsApp {a.get('to', '')} ({a.get('number', '?')}): \"{a.get('message', '')}\"",
)
def send_whatsapp(ctx: Context, args: dict) -> str:
    number = args.get("number") or _freeze_whatsapp(ctx, args)["number"]
    digits = "".join(ch for ch in str(number) if ch.isdigit())
    message = str(args.get("message", "")).strip()
    if not digits or not message:
        raise ToolError("I need a number and a message.")
    text = quote(message, safe="")
    app_link = f"whatsapp://send?phone={digits}&text={text}"
    web_link = f"https://web.whatsapp.com/send?phone={digits}&text={text}"
    os_name = system()
    typed = f"The message to {args.get('to')} is typed in WhatsApp; press Enter to send it."
    if os_name == "Darwin":
        was_running = _whatsapp_running()
        if run(["open", app_link]).returncode != 0:
            webbrowser.open(web_link)
            return f"Opened WhatsApp Web with the message to {args.get('to')}; press Enter to send it."
        if not was_running:
            # Starting from cold, WhatsApp may still be loading or showing another chat:
            # pressing Enter then could send something else to someone else.
            return typed
        time.sleep(3)  # let WhatsApp switch to the chat with the message typed in
        try:
            front = osascript('tell application "System Events" to get name of first process whose frontmost is true')
            if front != "WhatsApp":
                return typed
            osascript('tell application "System Events" to tell process "WhatsApp" to key code 36')  # Return
        except ToolError:
            return f"{typed} (To let Jarvis press Enter for you: {ACCESSIBILITY_HELP})"
        return f"Sent your WhatsApp message to {args.get('to')}."
    if os_name == "Windows":
        import os

        try:
            os.startfile(app_link)  # type: ignore[attr-defined]
        except OSError:
            webbrowser.open(web_link)
            return f"Opened WhatsApp Web with the message to {args.get('to')}; press Enter to send it."
        # Windows can't safely tell which window would get the Enter key (a browser tab
        # called "WhatsApp" could), so the last step is the user's.
        return typed
    webbrowser.open(web_link)
    return f"Opened WhatsApp Web with the message to {args.get('to')}; press Enter to send it."
