@echo off
setlocal
set START_DIR=%cd%
set SCRIPT_PATH=%~f0
for %%I in ("%SCRIPT_PATH%") do set SCRIPT_DIR=%%~dpI
cd /d %SCRIPT_DIR%\..

where py >nul 2>nul
if %ERRORLEVEL%==0 (
  py -3.11 --version >nul 2>nul
  if %ERRORLEVEL%==0 (
    set PYTHON_CMD=py -3.11
  ) else (
    set PYTHON_CMD=python
  )
) else (
  set PYTHON_CMD=python
)

if not exist .venv %PYTHON_CMD% -m venv .venv
call .venv\Scripts\activate
python -m pip install --upgrade pip
pip install -r requirements.txt
if not exist config\.env copy config\.env.example config\.env
set PYTHONPATH=%cd%\src
python -m meeting_skill.cli doctor
python -m meeting_skill.cli --help
cd /d %START_DIR%
