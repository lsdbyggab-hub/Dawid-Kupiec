@echo off
setlocal
cd /d "%~dp0"

set "CODEX_PY=C:\Users\dawid\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe"

if exist "%CODEX_PY%" (
  "%CODEX_PY%" run_app.py
  exit /b %ERRORLEVEL%
)

py -3 run_app.py
if %ERRORLEVEL% EQU 0 exit /b 0

python run_app.py
