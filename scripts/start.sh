#!/usr/bin/env sh
# Start Jarvis on your own Mac or Linux computer: ./scripts/start.sh
set -e
cd "$(dirname "$0")/.."
if [ ! -f .venv/.installed ]; then
  echo "Setting up Jarvis (first run takes a minute)…"
  python3 -m venv .venv
  .venv/bin/pip install -q --upgrade pip
  .venv/bin/pip install -q -r requirements.txt
  touch .venv/.installed
fi
[ -f .env ] || { cp .env.example .env; echo "Created .env - open it and paste your ANTHROPIC_API_KEY, then run this again."; exit 1; }
PORT="${PORT:-8000}"
echo "Jarvis is starting at http://localhost:$PORT  (press Ctrl+C to stop)"
( sleep 3; (command -v open >/dev/null && open "http://localhost:$PORT") || (command -v xdg-open >/dev/null && xdg-open "http://localhost:$PORT") || true ) &
exec .venv/bin/uvicorn jarvis.server:app --host 127.0.0.1 --port "$PORT" --no-access-log --timeout-graceful-shutdown 3
