"""Computer control. Only available when JARVIS_MODE=local, i.e. when Jarvis runs
on your own machine. Works on Windows, macOS and Linux."""

from __future__ import annotations

import os
import platform
import re
import shutil
import subprocess
import sys
import webbrowser
from datetime import datetime
from pathlib import Path

from jarvis.tools import Context, ToolError, tool

MAX_OUTPUT = 4000
SAFE_APP_NAME = re.compile(r"^[\w .+&'-]{1,80}$")


def safe_path(ctx: Context, path: str) -> Path:
    """Resolve a path and make sure it stays inside JARVIS_FILES_ROOT."""
    root = ctx.settings.files_root.expanduser().resolve()
    raw = Path(path or ".").expanduser()
    full = (raw if raw.is_absolute() else root / raw).resolve()
    if full != root and root not in full.parents:
        raise ToolError(f"I can only access files inside {root}.")
    # Hidden files and folders (.ssh, .aws, .env, …) hold passwords and keys: off limits.
    if any(part.startswith(".") for part in full.relative_to(root).parts):
        raise ToolError("Hidden files and folders are off limits.")
    return full


def clip(text: str) -> str:
    return text if len(text) <= MAX_OUTPUT else text[:MAX_OUTPUT] + "\n…(truncated)"


@tool(
    "open_url",
    "Open a web page in the user's browser. The user approves it in the app.",
    {"url": {"type": "string"}},
    ["url"],
    local_only=True,
    needs_approval=True,
    summarize=lambda ctx, a: f"Open in your browser: {a.get('url', '')}",
)
def open_url(ctx: Context, args: dict) -> str:
    url = args["url"].strip()
    if not url.startswith(("http://", "https://")):
        url = "https://" + url
    webbrowser.open(url)
    return f"Opened {url}."


@tool(
    "open_app",
    "Launch an application on the user's computer by name, e.g. 'Spotify', 'Calculator', "
    "'notepad'. The user approves it in the app.",
    {"name": {"type": "string"}},
    ["name"],
    local_only=True,
    needs_approval=True,
    summarize=lambda ctx, a: f"Open the app: {a.get('name', '')}",
)
def open_app(ctx: Context, args: dict) -> str:
    name = args["name"].strip()
    if not SAFE_APP_NAME.match(name):
        raise ToolError("That doesn't look like an app name.")
    system = platform.system()
    try:
        if system == "Darwin":
            subprocess.run(["open", "-a", name], check=True, capture_output=True, timeout=20)
        elif system == "Windows":
            os.startfile(shutil.which(name) or name)  # type: ignore[attr-defined]
        else:
            exe = shutil.which(name) or shutil.which(name.lower())
            if not exe:
                raise ToolError(f"Couldn't find an app called '{name}'.")
            subprocess.Popen([exe], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, start_new_session=True)
    except (OSError, subprocess.CalledProcessError) as exc:
        raise ToolError(f"Couldn't open '{name}': {exc}") from exc
    return f"Opened {name}."


def _summarize_command(ctx: Context, args: dict) -> str:
    return f"Run on your computer: {args.get('command', '')}"


@tool(
    "run_command",
    "Run a shell command on the user's computer and return its output "
    f"({'PowerShell/cmd' if sys.platform == 'win32' else 'shell'}). The user must "
    "approve every command; the app asks them automatically.",
    {"command": {"type": "string"}},
    ["command"],
    local_only=True,
    needs_approval=True,
    summarize=_summarize_command,
)
def run_command(ctx: Context, args: dict) -> str:
    try:
        proc = subprocess.run(
            args["command"],
            shell=True,
            capture_output=True,
            text=True,
            timeout=120,
            cwd=str(ctx.settings.files_root.expanduser()),
        )
    except subprocess.TimeoutExpired as exc:
        raise ToolError("The command took longer than 2 minutes and was stopped.") from exc
    output = (proc.stdout + ("\n" + proc.stderr if proc.stderr else "")).strip() or "(no output)"
    return clip(f"Exit code {proc.returncode}\n{output}")


@tool(
    "list_files",
    "List the files in a folder on the user's computer (relative to their home/work folder).",
    {"path": {"type": "string", "description": "Folder path; default is the root folder."}},
    local_only=True,
)
def list_files(ctx: Context, args: dict) -> str:
    folder = safe_path(ctx, args.get("path") or ".")
    if not folder.is_dir():
        raise ToolError(f"{folder} is not a folder.")
    entries = sorted(folder.iterdir(), key=lambda p: (not p.is_dir(), p.name.lower()))
    lines = [f"{'[dir] ' if p.is_dir() else ''}{p.name}" for p in entries[:200] if not p.name.startswith(".")]
    return clip(f"{folder}:\n" + ("\n".join(lines) or "(empty)"))


@tool(
    "read_file",
    "Read a text file on the user's computer.",
    {"path": {"type": "string"}},
    ["path"],
    local_only=True,
)
def read_file(ctx: Context, args: dict) -> str:
    path = safe_path(ctx, args["path"])
    if not path.is_file():
        raise ToolError(f"{path} is not a file.")
    try:
        text = path.read_text(encoding="utf-8")
    except UnicodeDecodeError as exc:
        raise ToolError("That isn't a text file.") from exc
    return text[:20000] + ("\n…(truncated)" if len(text) > 20000 else "")


@tool(
    "write_file",
    "Create or overwrite a text file on the user's computer. The user must approve.",
    {"path": {"type": "string"}, "content": {"type": "string"}},
    ["path", "content"],
    local_only=True,
    needs_approval=True,
    summarize=lambda ctx, a: f"Write {len(a.get('content', ''))} characters to {a.get('path', '')}",
)
def write_file(ctx: Context, args: dict) -> str:
    path = safe_path(ctx, args["path"])
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(args["content"], encoding="utf-8")
    return f"Wrote {path}."


@tool("system_info", "Information about the user's computer: OS, disk space, time.", local_only=True)
def system_info(ctx: Context, args: dict) -> str:
    usage = shutil.disk_usage(ctx.settings.files_root.expanduser())
    gb = 1024**3
    return (
        f"OS: {platform.system()} {platform.release()} ({platform.machine()})\n"
        f"Computer name: {platform.node()}\n"
        f"Disk: {usage.free / gb:.1f} GB free of {usage.total / gb:.1f} GB\n"
        f"Local time: {datetime.now().astimezone().strftime('%Y-%m-%d %H:%M %Z')}"
    )
