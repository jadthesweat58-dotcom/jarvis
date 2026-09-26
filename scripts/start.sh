#!/usr/bin/env sh
# Start Jarvis on your own Mac or Linux computer: ./scripts/start.sh
set -e
cd "$(dirname "$0")/.."
if [ ! -d .venv ]; then
  echo "First run: setting up Jarvis (this takes a minute)…"
  python3 -m venv .venv
  .venv/bin/pip install -q --upgrade pip
  .venv/bin/pip install -q -r requirements.txt
fi
[ -f .env ] || { cp .env.example .env; echo "Created .env - open it and paste your ANTHROPIC_API_KEY, then run this again."; exit 1; }
PORT="${PORT:-8000}"
echo "Jarvis is starting at http://localhost:$PORT"
( sleep 2; (command -v open >/dev/null && open "http://localhost:$PORT") || (command -v xdg-open >/dev/null && xdg-open "http://localhost:$PORT") || true ) &
exec .venv/bin/uvicorn jarvis.server:app --host 127.0.0.1 --port "$PORT"
