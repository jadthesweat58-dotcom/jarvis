"""Jarvis in your menu bar (Mac) or system tray (Windows).

One small app that runs everything in the background: the Jarvis server, and
clap-to-open listening. Its icon menu opens the dashboard, plays today's
briefing, switches clap listening on or off, and quits.

    python -m jarvis.tray          # or let it start at login: python -m jarvis.autostart install
"""

from __future__ import annotations

import logging
import os
import socket
import sys
import threading
import webbrowser
from pathlib import Path

log = logging.getLogger("jarvis.tray")
ICON = Path(__file__).parent / "static" / "icons" / "icon-192.png"


def port_in_use(port: int) -> bool:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.settimeout(0.5)
        return s.connect_ex(("127.0.0.1", port)) == 0


class Jarvis:
    def __init__(self) -> None:
        from jarvis.clap import settings_from_env
        from jarvis.config import settings

        self.settings = settings
        self.port = int(os.environ.get("PORT", "8000") or 8000)
        self.url = f"http://localhost:{self.port}"
        _, self.sensitivity, self.briefing = settings_from_env()
        self.server = None
        self.clap = None

    # --- the server -----------------------------------------------------------
    def start_server(self) -> None:
        if port_in_use(self.port):
            log.info("Jarvis is already running on port %s; using that one.", self.port)
            return
        import uvicorn

        config = uvicorn.Config("jarvis.server:app", host="127.0.0.1", port=self.port, access_log=False,
                                timeout_graceful_shutdown=3, log_level="warning")
        self.server = uvicorn.Server(config)
        threading.Thread(target=self.server.run, name="jarvis-server", daemon=True).start()
        threading.Thread(target=self._check_started, daemon=True).start()

    def _check_started(self) -> None:
        import time

        for _ in range(60):
            if port_in_use(self.port):
                return
            time.sleep(0.5)
        self.notify("Jarvis's server didn't start. Check ~/Library/Logs/Jarvis.log (or run scripts/start.sh).")

    # --- clapping ---------------------------------------------------------------
    def clapped(self) -> None:
        from jarvis.clap import open_jarvis

        open_jarvis(self.url, self.settings.my_name, self.briefing, self.settings.access_token)

    def toggle_clap(self, *_: object) -> None:
        try:
            if self.clap and self.clap.running:
                self.clap.stop()
                return
            if self.clap is None:
                from jarvis.clap import ClapListener

                self.clap = ClapListener(self.clapped, self.sensitivity)
            self.clap.start()
        except Exception as exc:  # no microphone packages, no permission, …
            log.warning("Clap listening unavailable: %s", exc)
            self.notify(f"Can't listen for claps: {exc}")

    @property
    def listening(self) -> bool:
        return bool(self.clap and self.clap.running)

    # --- menu actions -------------------------------------------------------------
    def open_dashboard(self, *_: object) -> None:
        webbrowser.open(self.url)

    def play_briefing(self, *_: object) -> None:
        from jarvis.clap import fetch_briefing, say

        def run() -> None:
            text = fetch_briefing(self.url, self.settings.access_token)
            say(text or "Sorry, I couldn't get the briefing just now.")

        threading.Thread(target=run, daemon=True).start()

    def notify(self, text: str) -> None:
        icon = getattr(self, "icon", None)
        try:
            if icon is not None:
                icon.notify(text, "Jarvis")
        except Exception:
            pass

    def quit(self, icon=None, *_: object) -> None:
        if self.clap:
            self.clap.stop()
        if self.server:
            self.server.should_exit = True
        if icon is not None:
            icon.stop()

    # --- run -------------------------------------------------------------------
    def menu(self):
        import pystray

        return pystray.Menu(
            pystray.MenuItem("Open Jarvis", self.open_dashboard, default=True),
            pystray.MenuItem("Listen for claps", self.toggle_clap, checked=lambda item: self.listening),
            pystray.MenuItem("Hear today's briefing", self.play_briefing),
            pystray.Menu.SEPARATOR,
            pystray.MenuItem("Quit Jarvis", self.quit),
        )

    def run(self) -> None:
        try:
            import pystray
            from PIL import Image
        except ImportError:
            # Exit "successfully" so the start-at-login service doesn't keep restarting it.
            log.error("The menu-bar app needs its packages. Run: pip install -r requirements-local.txt")
            sys.exit(0)
        if not single_instance():
            log.info("Jarvis is already running in the menu bar.")
            webbrowser.open(self.url)
            sys.exit(0)
        self.start_server()
        if os.environ.get("CLAP_ON_START", "on").strip().lower() not in ("off", "0", "no", "false"):
            self.toggle_clap()
        self.icon = pystray.Icon("Jarvis", Image.open(ICON), "Jarvis", menu=self.menu())
        self.icon.run()


_instance_lock = None


def single_instance(port: int = 47863) -> bool:
    """True for the first copy of the menu-bar app; a second copy finds the port taken."""
    global _instance_lock
    lock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    try:
        lock.bind(("127.0.0.1", port))
    except OSError:
        lock.close()
        return False
    _instance_lock = lock  # held for as long as the app runs
    return True


def main() -> None:
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(name)s: %(message)s")
    # Web libraries log full addresses at INFO, and some carry secrets (bot token, calendar link).
    for noisy in ("httpx", "httpcore", "urllib3"):
        logging.getLogger(noisy).setLevel(logging.WARNING)
    Jarvis().run()


if __name__ == "__main__":
    main()
