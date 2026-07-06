@echo off
setlocal
cd /d %~dp0
if not exist .env (
  echo .env not found. Copy env.local.example to .env first.
  exit /b 1
)
echo .env path: %cd%\.env
for /f "usebackq tokens=1,* delims==" %%A in (".env") do (
  echo %%A | findstr /I "KEY TOKEN SECRET" >nul
  if errorlevel 1 (
    echo %%A=%%B
  ) else (
    echo %%A=***
  )
)
