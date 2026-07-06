@echo off
setlocal
set SCRIPT_DIR=%~dp0
cd /d %SCRIPT_DIR%\..
if not exist .venv\Scripts\python.exe (
  echo Project virtual environment not found. Run scripts\setup.bat first.
  exit /b 1
)
call .venv\Scripts\activate
set PYTHONPATH=%cd%\src
python -m meeting_skill.cli %*
