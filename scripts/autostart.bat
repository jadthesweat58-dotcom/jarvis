@echo off
rem Start Jarvis automatically when you sign in to Windows (tray icon + clap to open).
rem Double-click this file once. To undo, run:  scripts\autostart.bat off
cd /d "%~dp0\.."
if not exist .venv\.installed-local (
  echo Setting up Jarvis for this computer ^(first run takes a minute^)...
  if not exist .venv ( py -3 -m venv .venv || python -m venv .venv )
  .venv\Scripts\python -m pip install -q --upgrade pip
  .venv\Scripts\python -m pip install -q -r requirements-local.txt || goto :failed
  type nul > .venv\.installed
  type nul > .venv\.installed-local
)
if not exist .env (
  copy .env.example .env >nul
  echo Created .env - paste your GEMINI_API_KEY into it, save, then run this again.
  notepad .env
  pause
  exit /b 1
)
if "%1"=="off" ( .venv\Scripts\python -m jarvis.autostart uninstall ) else ( .venv\Scripts\python -m jarvis.autostart install )
pause
exit /b 0

:failed
echo Installing Jarvis's packages failed. Check your internet connection and try again.
pause
exit /b 1
