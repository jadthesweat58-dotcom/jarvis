#!/usr/bin/env sh
# Start Jarvis automatically when you log in to your Mac (menu-bar icon + clap to open).
# Double-click this file once. To undo: ./scripts/autostart.command off
set -e
cd "$(dirname "$0")/.."
. scripts/_setup.sh
setup_jarvis
if [ "$1" = "off" ]; then exec .venv/bin/python -m jarvis.autostart uninstall; fi
.venv/bin/python -m jarvis.autostart install
echo "The first time, macOS may ask to let Python use the microphone: click Allow."
