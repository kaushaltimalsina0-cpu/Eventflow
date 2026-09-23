@echo off
title EventFlow Setup and Run
cd /d "%~dp0"

echo ==========================================
echo        EventFlow Event Management
echo ==========================================
echo.

where py >nul 2>nul
if %errorlevel%==0 (
    set "PY=py"
) else (
    where python >nul 2>nul
    if %errorlevel%==0 (
        set "PY=python"
    ) else (
        echo ERROR: Python is not installed or not in PATH.
        echo Install Python from https://www.python.org/downloads/
        echo Make sure "Add Python to PATH" is checked.
        pause
        exit /b 1
    )
)

if not exist ".venv\Scripts\python.exe" (
    echo [1/3] Creating virtual environment...
    %PY% -m venv .venv
    if errorlevel 1 goto :error
)

echo [2/3] Installing required packages...
".venv\Scripts\python.exe" -m pip install -r requirements.txt
if errorlevel 1 goto :error

echo [3/3] Starting EventFlow...
echo.
echo Open http://127.0.0.1:5000 in your browser.
echo.
echo Login:
echo   Admin: admin@example.com / admin123
echo   Member: member@example.com / member123
echo.
echo Keep this window open while using the software.
echo Press Ctrl+C to stop the server.
echo.
".venv\Scripts\python.exe" app.py
goto :eof

:error
echo.
echo Something went wrong during setup.
echo Read the error above and send me a screenshot.
pause
