# Shared by the Mac/Linux scripts: find a Python that's new enough, then set up
# Jarvis's private Python environment (.venv) with everything it needs.

find_python() {
  for candidate in python3.13 python3.12 python3.11 python3.10 python3 \
      /opt/homebrew/bin/python3 /usr/local/bin/python3 \
      /Library/Frameworks/Python.framework/Versions/Current/bin/python3; do
    if command -v "$candidate" >/dev/null 2>&1 && \
       "$candidate" -c 'import sys; sys.exit(0 if sys.version_info >= (3, 10) else 1)' 2>/dev/null; then
      command -v "$candidate"
      return 0
    fi
  done
  return 1
}

setup_jarvis() {
  # A .venv made by an old Python can't run Jarvis: start that one over.
  if [ -x .venv/bin/python ] && ! .venv/bin/python -c 'import sys; sys.exit(0 if sys.version_info >= (3, 10) else 1)' 2>/dev/null; then
    rm -rf .venv
  fi
  if [ ! -f .venv/.installed-local ]; then
    PYTHON="$(find_python)" || {
      echo ""
      echo "Jarvis needs Python 3.10 or newer, and this computer only has an older one."
      echo "Install Python 3.12 from https://www.python.org/downloads/ (click the big yellow"
      echo "Download button, open the file, click Continue until it's done), then run this again."
      exit 1
    }
    echo "Setting up Jarvis with $("$PYTHON" --version) (first run takes a few minutes)…"
    [ -d .venv ] || "$PYTHON" -m venv .venv
    .venv/bin/python -m pip install -q --upgrade pip
    .venv/bin/python -m pip install -q -r requirements-local.txt || {
      echo "Installing Jarvis's packages failed. Check your internet connection and try again."
      exit 1
    }
    touch .venv/.installed .venv/.installed-local
  fi
  if [ ! -f .env ]; then
    cp .env.example .env
    echo "Created .env - open it, paste your GEMINI_API_KEY (and the other settings), save, then run this again."
    (command -v open >/dev/null && open -e .env) || true
    exit 1
  fi
}
