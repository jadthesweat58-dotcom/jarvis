#!/usr/bin/env sh
# Start Jarvis on your own Mac or Linux computer: ./scripts/start.sh
set -e
cd "$(dirname "$0")/.."
. scripts/_setup.sh
setup_jarvis
PORT="${PORT:-8000}"
echo "Jarvis is starting at http://localhost:$PORT  (press Ctrl+C to stop)"
( sleep 3; (command -v open >/dev/null && open "http://localhost:$PORT") || (command -v xdg-open >/dev/null && xdg-open "http://localhost:$PORT") || true ) &
exec .venv/bin/python -m uvicorn jarvis.server:app --host 127.0.0.1 --port "$PORT" --no-access-log --timeout-graceful-shutdown 3
