#!/usr/bin/env sh
# Clap twice to open Jarvis (Mac): double-click this file, or run ./scripts/clap.command
# The first time, macOS asks to let Terminal use the microphone: click Allow.
set -e
cd "$(dirname "$0")/.."
. scripts/_setup.sh
setup_jarvis
exec .venv/bin/python -m jarvis.clap "$@"
