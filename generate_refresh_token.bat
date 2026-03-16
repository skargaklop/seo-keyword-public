@echo off
chcp 65001 >nul 2>&1
echo ============================================================
echo   Google Ads - Генерация Refresh Token
echo ============================================================
echo.

python --version >nul 2>&1
if %ERRORLEVEL% NEQ 0 (
    echo [ERROR] Python не найден. Установите Python и добавьте в PATH.
    pause
    exit /b 1
)

echo [INFO] Проверяю зависимости...
python -c "import google_auth_oauthlib" >nul 2>&1
if %ERRORLEVEL% NEQ 0 (
    echo [INFO] Устанавливаю google-auth-oauthlib...
    pip install google-auth-oauthlib
)

python -c "import dotenv" >nul 2>&1
if %ERRORLEVEL% NEQ 0 (
    echo [INFO] Устанавливаю python-dotenv...
    pip install python-dotenv
)

echo.
echo [INFO] Запускаю генерацию токена...
echo.
python "%~dp0generate_refresh_token.py"

echo.
pause
