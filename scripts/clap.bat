@echo off
rem Clap twice to open Jarvis (Windows): double-click this file.
cd /d "%~dp0\.."
if not exist .venv\.installed-local (
  echo Setting up clap-to-open ^(first run takes a minute^)...
  if not exist .venv ( py -3 -m venv .venv || python -m venv .venv )
  .venv\Scripts\python -m pip install -q --upgrade pip
  .venv\Scripts\python -m pip install -q -r requirements-local.txt || goto :failed
  type nul > .venv\.installed
  type nul > .venv\.installed-local
)
.venv\Scripts\python -m jarvis.clap %*
pause
exit /b 0

:failed
echo Installing the microphone packages failed. Check your internet connection and try again.
pause
exit /b 1
