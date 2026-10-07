@echo off
rem Shared by the Windows scripts: find Python 3.10 or newer, set up Jarvis's private
rem Python environment (.venv) with everything it needs, and make the .env settings file.
if exist .venv\Scripts\python.exe (
  .venv\Scripts\python -c "import sys; sys.exit(0 if sys.version_info >= (3, 10) else 1)" >nul 2>&1 || rmdir /s /q .venv
)
if exist .venv\.installed-local goto :env
set "PYEXE="
for %%v in (3.13 3.12 3.11 3.10) do (
  if not defined PYEXE ( py -%%v -c "pass" >nul 2>&1 && set "PYEXE=py -%%v" )
)
if not defined PYEXE (
  python -c "import sys; sys.exit(0 if sys.version_info >= (3, 10) else 1)" >nul 2>&1 && set "PYEXE=python"
)
if not defined PYEXE (
  echo.
  echo Jarvis needs Python 3.10 or newer. Install Python 3.12 from https://www.python.org/downloads/
  echo ^(in the installer, tick "Add python.exe to PATH"^), then run this again.
  exit /b 1
)
echo Setting up Jarvis ^(first run takes a few minutes^)...
if not exist .venv ( %PYEXE% -m venv .venv || exit /b 1 )
.venv\Scripts\python -m pip install -q --upgrade pip
.venv\Scripts\python -m pip install -q -r requirements-local.txt
if errorlevel 1 (
  echo Installing Jarvis's packages failed. Check your internet connection and try again.
  exit /b 1
)
type nul > .venv\.installed
type nul > .venv\.installed-local
:env
if not exist .env (
  copy .env.example .env >nul
  echo Created .env - paste your GEMINI_API_KEY into it, save, then run this again.
  notepad .env
  exit /b 1
)
exit /b 0
