@echo off
rem Start Jarvis automatically when you sign in to Windows (tray icon + clap to open).
rem Double-click this file once. To undo, run:  scripts\autostart.bat off
cd /d "%~dp0\.."
call scripts\_setup.bat || ( pause & exit /b 1 )
if "%1"=="off" ( .venv\Scripts\python -m jarvis.autostart uninstall ) else ( .venv\Scripts\python -m jarvis.autostart install )
pause
