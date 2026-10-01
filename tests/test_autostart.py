import plistlib
import sys
import types
from pathlib import Path

from jarvis import autostart, tray


def test_mac_launch_agent(tmp_path):
    data = plistlib.loads(autostart.mac_plist(home=tmp_path))
    assert data["Label"] == "com.jarvis.assistant"
    assert data["ProgramArguments"][1:] == ["-m", "jarvis.tray"] and Path(data["ProgramArguments"][0]).name.startswith("python")
    assert data["RunAtLoad"] is True and data["KeepAlive"] == {"SuccessfulExit": False}
    assert data["WorkingDirectory"] == str(autostart.REPO)
    assert data["StandardErrorPath"] == str(tmp_path / "Library" / "Logs" / "Jarvis.log")


def test_windows_launcher_quotes_paths(monkeypatch):
    monkeypatch.setattr(autostart, "REPO", Path('C:/Users/Jad "J"/jarvis'))
    monkeypatch.setattr(autostart, "python_path", lambda windowed=False: "C:/Py/pythonw.exe")
    text = autostart.windows_launcher()
    assert 'shell.CurrentDirectory = "C:/Users/Jad ""J""/jarvis"' in text
    assert 'shell.Run """C:/Py/pythonw.exe"" -m jarvis.tray", 0, False' in text


def test_tray_menu_and_clap_toggle(monkeypatch):
    items = []
    fake_pystray = types.SimpleNamespace(
        Menu=lambda *entries: entries, MenuItem=lambda text, action, **kw: items.append((text, kw)) or (text, action))
    fake_pystray.Menu.SEPARATOR = "---"
    monkeypatch.setitem(sys.modules, "pystray", fake_pystray)
    app = tray.Jarvis()
    menu = app.menu()
    assert [m[0] for m in menu if m != "---"] == ["Open Jarvis", "Listen for claps", "Hear today's briefing", "Quit Jarvis"]

    class FakeListener:
        running = False

        def __init__(self, cb, sensitivity):
            pass

        def start(self):
            self.running = True

        def stop(self):
            self.running = False

    monkeypatch.setattr("jarvis.clap.ClapListener", FakeListener)
    app.toggle_clap()
    assert app.listening
    app.toggle_clap()
    assert not app.listening


def test_tray_reuses_a_running_server(monkeypatch):
    monkeypatch.setattr(tray, "port_in_use", lambda port: True)
    app = tray.Jarvis()
    app.start_server()
    assert app.server is None
