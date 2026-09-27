#!/usr/bin/env sh
# Clap twice to open Jarvis (Mac): double-click this file, or run ./scripts/clap.command
# The first time, macOS asks to let Terminal use the microphone: click Allow.
set -e
cd "$(dirname "$0")/.."
if [ ! -f .venv/.installed-local ]; then
  echo "Setting up clap-to-open (first run takes a minute)…"
  [ -d .venv ] || python3 -m venv .venv
  .venv/bin/pip install -q --upgrade pip
  .venv/bin/pip install -q -r requirements-local.txt
  touch .venv/.installed .venv/.installed-local
fi
exec .venv/bin/python -m jarvis.clap "$@"
