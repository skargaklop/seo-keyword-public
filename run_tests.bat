@echo off
setlocal enabledelayedexpansion

cd /d "%~dp0"

echo ===================================================
echo       Auto SEO Keyword Planner — Tests
echo ===================================================
echo.

REM Check dependencies
python -c "import pytest" >nul 2>&1
if !ERRORLEVEL! NEQ 0 (
    echo [INFO] pytest not found. Installing dependencies...
    pip install -r requirements.txt
)

echo [INFO] Running tests...
echo.

python -m pytest tests/ -v

echo.
echo ===================================================
echo       Tests completed.
echo ===================================================

endlocal
pause
