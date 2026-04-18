@echo off
title Metadata Restore Tool — Setup
color 0A

echo.
echo ============================================================
echo   Google Takeout Metadata Restore Tool — Setup
echo ============================================================
echo.

REM ── Check Python ──
echo [1/3] Checking Python...
python --version >nul 2>&1
if errorlevel 1 (
    echo.
    echo   ERROR: Python was not found on your PATH.
    echo.
    echo   Please download and install Python 3.9+ from:
    echo   https://www.python.org/downloads/
    echo.
    echo   IMPORTANT: During install, check "Add Python to PATH"
    echo.
    pause
    exit /b 1
)
for /f "tokens=*" %%i in ('python --version') do echo   Found: %%i

echo.

REM ── Check exiftool ──
echo [2/3] Checking exiftool...
exiftool -ver >nul 2>&1
if errorlevel 1 (
    echo.
    echo   WARNING: exiftool was not found on your PATH.
    echo.
    echo   Please download it from: https://exiftool.org
    echo.
    echo   Windows setup steps:
    echo     1. Download "exiftool-XX.XX_64.zip"
    echo     2. Extract it — you will get "exiftool(-k).exe"
    echo     3. Rename it to "exiftool.exe"
    echo     4. Place it in C:\Windows\  (or any folder on your PATH)
    echo     5. Open a NEW Command Prompt and type:  exiftool -ver
    echo        to confirm it works.
    echo.
    echo   You can still install Python packages now and add exiftool later.
    echo.
) else (
    for /f "tokens=*" %%i in ('exiftool -ver') do echo   Found: exiftool %%i
)

echo.

REM ── Install Python packages ──
echo [3/3] Installing Python packages...
python -m pip install --upgrade pip --quiet
python -m pip install tqdm --quiet
if errorlevel 1 (
    echo   WARNING: Could not install tqdm. The tool will still work without it.
) else (
    echo   tqdm installed OK (progress bar for CLI mode).
)

echo.
echo ============================================================
echo   Setup complete!
echo.
echo   To launch the tool, run:
echo     python main.py
echo.
echo   Or double-click "launch.bat"
echo ============================================================
echo.
pause
