@echo off
setlocal

cd /d "%~dp0"

echo [JNotebookLM] Preparing local environment...

where python >nul 2>nul
if errorlevel 1 (
  echo [ERROR] Python was not found in PATH.
  echo Install Python 3.13+ first, then run this script again.
  exit /b 1
)

if not exist ".venv\Scripts\python.exe" (
  echo [JNotebookLM] Creating virtual environment...
  python -m venv .venv
  if errorlevel 1 (
    echo [ERROR] Failed to create .venv
    exit /b 1
  )
)

echo [JNotebookLM] Upgrading pip...
".venv\Scripts\python.exe" -m pip install --upgrade pip
if errorlevel 1 (
  echo [ERROR] Failed to upgrade pip
  exit /b 1
)

echo [JNotebookLM] Installing Python dependencies...
".venv\Scripts\python.exe" -m pip install -r requirements.txt
if errorlevel 1 (
  echo [ERROR] Failed to install requirements.txt
  exit /b 1
)

echo.
where ffmpeg >nul 2>nul
if errorlevel 1 (
  echo [WARN] ffmpeg not found in PATH. Video-to-audio STT will not work until ffmpeg is installed.
) else (
  echo [OK] ffmpeg detected.
)

where tesseract >nul 2>nul
if errorlevel 1 (
  echo [WARN] tesseract not found in PATH. Image OCR will not work until Tesseract OCR is installed.
) else (
  echo [OK] tesseract detected.
)

echo.
echo [DONE] Installation complete.
echo Start the app with:
echo   python run.py

exit /b 0
