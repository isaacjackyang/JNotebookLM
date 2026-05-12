@echo off
setlocal

cd /d "%~dp0"

if not exist ".venv\Scripts\python.exe" (
  echo [ERROR] Project virtual environment not found.
  echo Run install.cmd first:
  echo   .\install.cmd
  exit /b 1
)

set "JNOTEBOOKLM_PORT=7000"

echo [JNotebookLM] Starting on http://127.0.0.1:%JNOTEBOOKLM_PORT%/
python run.py
