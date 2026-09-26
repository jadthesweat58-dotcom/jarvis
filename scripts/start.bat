@echo off
rem Start Jarvis on your Windows computer: double-click this file.
cd /d "%~dp0\.."
if not exist .venv\.installed (
  echo Setting up Jarvis ^(first run takes a minute^)...
  py -3 -m venv .venv || python -m venv .venv
  .venv\Scripts\python -m pip install -q --upgrade pip
  .venv\Scripts\python -m pip install -q -r requirements.txt || goto :failed
  type nul > .venv\.installed
)
if not exist .env (
  copy .env.example .env >nul
  echo Created .env - paste your ANTHROPIC_API_KEY into it, save, then run this again.
  notepad .env
  pause
  exit /b 1
)
if "%PORT%"=="" set PORT=8000
echo Jarvis is starting at http://localhost:%PORT%  (close this window to stop)
start "" cmd /c "timeout /t 4 >nul & start http://localhost:%PORT%"
.venv\Scripts\python -m uvicorn jarvis.server:app --host 127.0.0.1 --port %PORT% --no-access-log --timeout-graceful-shutdown 3
pause
exit /b 0

:failed
echo Installing Jarvis's packages failed. Check your internet connection and try again.
pause
exit /b 1
