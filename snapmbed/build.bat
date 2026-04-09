@echo off
REM SnapMbed — build standalone .exe
REM Run this from the snapmbed/ folder after installing requirements.txt

echo [1/3] Installing dependencies...
pip install -r requirements.txt

echo [2/3] Building executable...
pyinstaller ^
  --onefile ^
  --windowed ^
  --name "SnapMbed" ^
  --icon=icon.ico ^
  --add-data "gui;gui" ^
  --add-data "core;core" ^
  snapmbed.py

echo [3/3] Done! Find SnapMbed.exe in the dist/ folder.
pause
