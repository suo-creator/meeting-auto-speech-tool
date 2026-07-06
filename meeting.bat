@echo off
setlocal
set ROOT=%~dp0
if not exist "%ROOT%.venv\Scripts\python.exe" (
  echo Project virtual environment not found. Run "%ROOT%scripts\setup.bat" first.
  exit /b 1
)
set PYTHONPATH=%ROOT%src
"%ROOT%.venv\Scripts\python.exe" -m meeting_skill.cli %*
