@echo off
setlocal
cd /d "%~dp0\.."
if not exist .venv\Scripts\python.exe (
  echo Project virtual environment not found. Run scripts\setup.bat first.
  exit /b 1
)
call .venv\Scripts\activate
set PYTHONPATH=%cd%\src
if exist dist\src rmdir /s /q dist\src
if exist dist\app_gui.exe del /q dist\app_gui.exe
python -m pip install pyinstaller
pyinstaller --clean --noconfirm app_gui.spec
if %ERRORLEVEL% neq 0 exit /b %ERRORLEVEL%
if exist dist\src rmdir /s /q dist\src
if exist dist\app_gui.exe del /q dist\app_gui.exe
if not exist dist\data\cache mkdir dist\data\cache
if not exist dist\data\cache\sessions mkdir dist\data\cache\sessions
if not exist dist\config mkdir dist\config
if exist config\.env copy /Y config\.env dist\config\.env >nul
if exist config\.env.example copy /Y config\.env.example dist\config\.env.example >nul
echo Built: dist\MeetingSpeechTool.exe
echo Runtime config: dist\config\.env
echo Runtime cache: dist\data\cache\sessions
