@echo off
rem Clap twice to open Jarvis (Windows): double-click this file.
cd /d "%~dp0\.."
call scripts\_setup.bat || ( pause & exit /b 1 )
.venv\Scripts\python -m jarvis.clap %*
pause
