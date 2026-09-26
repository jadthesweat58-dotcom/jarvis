@echo off
rem Start Jarvis on your Windows computer: double-click this file.
cd /d "%~dp0\.."
if not exist .venv (
  echo First run: setting up Jarvis ^(this takes a minute^)...
  py -3 -m venv .venv || python -m venv .venv
  .venv\Scripts\python -m pip install -q --upgrade pip
  .venv\Scripts\pip install -q -r requirements.txt
)
if not exist .env (
  copy .env.example .env >nul
  echo Created .env - open it in Notepad, paste your ANTHROPIC_API_KEY, then run this again.
  notepad .env
  pause
  exit /b 1
)
if "%PORT%"=="" set PORT=8000
echo Jarvis is starting at http://localhost:%PORT%
start "" http://localhost:%PORT%
.venv\Scripts\uvicorn jarvis.server:app --host 127.0.0.1 --port %PORT%
