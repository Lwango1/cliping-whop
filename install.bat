@echo off
title Betway Clipper - Installation
echo ========================================
echo   Betway Clipper - Setup
echo ========================================
echo.

echo [1/4] Installing Python dependencies...
pip install -r requirements.txt
if %errorlevel% neq 0 (
    echo Failed to install dependencies.
    pause
    exit /b 1
)

echo [2/4] Installing Playwright browsers...
python -m playwright install chromium
if %errorlevel% neq 0 (
    echo Failed to install Playwright browsers.
    pause
    exit /b 1
)

echo [3/4] Checking FFmpeg...
where ffmpeg >nul 2>&1
if %errorlevel% neq 0 (
    echo WARNING: FFmpeg not found in PATH.
    echo Download from: https://ffmpeg.org/download.html
    echo Make sure ffmpeg.exe is in your PATH.
)

echo [4/4] Setup complete!
echo.
echo Usage:
echo   python main.py setup     - First-time account configuration
echo   python main.py run       - Start the automated scheduler
echo   python main.py once      - Run one pipeline cycle
echo   python main.py apply     - Auto-apply to Whop campaigns
echo   python main.py status    - Show current configuration
echo.
pause
