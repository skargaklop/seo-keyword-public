@echo off
setlocal enabledelayedexpansion

cd /d "%~dp0"

echo ===================================================
echo       Auto SEO Keyword Planner Tests / Тесты Auto SEO Keyword Planner
echo ===================================================
echo.

REM Check dependencies
python -c "import pytest" >nul 2>&1
if !ERRORLEVEL! NEQ 0 (
    echo [INFO] Installing dependencies because pytest was not found / Устанавливаю зависимости, потому что pytest не найден...
    pip install -r requirements.txt
)

echo [INFO] Running tests / Запуск тестов...
echo.

python -m pytest tests/ -v

echo.
echo ===================================================
echo       Tests completed / Тесты завершены.
echo ===================================================

endlocal
pause
