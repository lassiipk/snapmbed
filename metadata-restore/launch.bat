@echo off
title Google Takeout — Metadata Restore Tool
cd /d "%~dp0"
python main.py
if errorlevel 1 (
    echo.
    echo Something went wrong. Make sure Python is installed and on your PATH.
    pause
)
