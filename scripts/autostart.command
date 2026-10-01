#!/usr/bin/env sh
# Start Jarvis automatically when you log in to your Mac (menu-bar icon + clap to open).
# Double-click this file once. To undo: ./scripts/autostart.command off
set -e
cd "$(dirname "$0")/.."
if [ ! -f .venv/.installed-local ]; then
  echo "Setting up Jarvis for this Mac (first run takes a minute)…"
  [ -d .venv ] || python3 -m venv .venv
  .venv/bin/pip install -q --upgrade pip
  .venv/bin/pip install -q -r requirements-local.txt
  touch .venv/.installed .venv/.installed-local
fi
[ -f .env ] || { cp .env.example .env; echo "Created .env - open it and paste your GEMINI_API_KEY, then run this again."; exit 1; }
if [ "$1" = "off" ]; then exec .venv/bin/python -m jarvis.autostart uninstall; fi
.venv/bin/python -m jarvis.autostart install
echo "The first time, macOS may ask to let Python use the microphone: click Allow."
