"""Start Jarvis (the menu-bar app: server + clap listening) when you log in.

    python -m jarvis.autostart install     # start at login, and start it now
    python -m jarvis.autostart uninstall   # stop starting at login
    python -m jarvis.autostart status

Mac: a LaunchAgent in ~/Library/LaunchAgents. Windows: a small launcher in your
Startup folder. Linux: an entry in ~/.config/autostart.
"""

from __future__ import annotations

import os
import platform
import plistlib
import subprocess
import sys
from pathlib import Path

LABEL = "com.jarvis.assistant"
REPO = Path(__file__).resolve().parent.parent


def python_path(windowed: bool = False) -> str:
    exe = Path(sys.executable)
    if windowed and platform.system() == "Windows":
        pythonw = exe.with_name("pythonw.exe")
        if pythonw.exists():
            return str(pythonw)  # no console window
    return str(exe)


def mac_plist_path(home: Path | None = None) -> Path:
    return (home or Path.home()) / "Library" / "LaunchAgents" / f"{LABEL}.plist"


def mac_plist(home: Path | None = None) -> bytes:
    log = str((home or Path.home()) / "Library" / "Logs" / "Jarvis.log")
    return plistlib.dumps({
        "Label": LABEL,
        "ProgramArguments": [python_path(), "-m", "jarvis.tray"],
        "WorkingDirectory": str(REPO),
        "RunAtLoad": True,
        "KeepAlive": {"SuccessfulExit": False},  # restart after a crash, not after "Quit Jarvis"
        "ProcessType": "Interactive",
        "StandardOutPath": log,
        "StandardErrorPath": log,
    })


def windows_startup_file() -> Path:
    return Path(os.environ.get("APPDATA", Path.home())) / "Microsoft" / "Windows" / "Start Menu" / "Programs" / "Startup" / "Jarvis.vbs"


def windows_launcher() -> str:
    q = lambda s: str(s).replace('"', '""')  # noqa: E731  (VBScript string quoting)
    return ('Set shell = CreateObject("WScript.Shell")\r\n'
            f'shell.CurrentDirectory = "{q(REPO)}"\r\n'
            f'shell.Run """{q(python_path(windowed=True))}"" -m jarvis.tray", 0, False\r\n')


def linux_desktop_file(home: Path | None = None) -> Path:
    return (home or Path.home()) / ".config" / "autostart" / "jarvis.desktop"


def install() -> str:
    system = platform.system()
    if system == "Darwin":
        path = mac_plist_path()
        path.parent.mkdir(parents=True, exist_ok=True)
        (Path.home() / "Library" / "Logs").mkdir(parents=True, exist_ok=True)
        path.write_bytes(mac_plist())
        domain = f"gui/{os.getuid()}"
        subprocess.run(["launchctl", "bootout", domain, str(path)], capture_output=True)
        subprocess.run(["launchctl", "bootstrap", domain, str(path)], capture_output=True, check=True)
        return "Jarvis will now start when you log in, and is starting now (look for its icon in the menu bar)."
    if system == "Windows":
        path = windows_startup_file()
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(windows_launcher(), encoding="utf-8")
        os.startfile(str(path))  # type: ignore[attr-defined]
        return "Jarvis will now start when you sign in, and is starting now (look for its icon by the clock)."
    path = linux_desktop_file()
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(f"[Desktop Entry]\nType=Application\nName=Jarvis\nPath={REPO}\n"
                    f"Exec={python_path()} -m jarvis.tray\nX-GNOME-Autostart-enabled=true\n")
    return "Jarvis will now start when you log in."


def uninstall() -> str:
    system = platform.system()
    if system == "Darwin":
        path = mac_plist_path()
        if path.exists():
            subprocess.run(["launchctl", "bootout", f"gui/{os.getuid()}", str(path)], capture_output=True)
            path.unlink()
    elif system == "Windows":
        windows_startup_file().unlink(missing_ok=True)
    else:
        linux_desktop_file().unlink(missing_ok=True)
    return "Jarvis won't start at login any more."


def status() -> str:
    system = platform.system()
    path = mac_plist_path() if system == "Darwin" else windows_startup_file() if system == "Windows" else linux_desktop_file()
    return "Starts at login: yes" if path.exists() else "Starts at login: no"


def main() -> None:
    command = (sys.argv[1:] or ["status"])[0]
    actions = {"install": install, "uninstall": uninstall, "status": status}
    if command not in actions:
        sys.exit("Use: python -m jarvis.autostart install | uninstall | status")
    print(actions[command]())


if __name__ == "__main__":
    main()
