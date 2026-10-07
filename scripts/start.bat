@echo off
rem Start Jarvis on your Windows computer: double-click this file.
cd /d "%~dp0\.."
call scripts\_setup.bat || ( pause & exit /b 1 )
if "%PORT%"=="" set PORT=8000
echo Jarvis is starting at http://localhost:%PORT%  (close this window to stop)
start "" cmd /c "timeout /t 4 >nul & start http://localhost:%PORT%"
.venv\Scripts\python -m uvicorn jarvis.server:app --host 127.0.0.1 --port %PORT% --no-access-log --timeout-graceful-shutdown 3
pause
