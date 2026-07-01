@echo off
chcp 65001 >nul 2>&1
echo ============================================================
echo   Google Ads Refresh Token Generation / Генерация Refresh Token Google Ads
echo ============================================================
echo.

python --version >nul 2>&1
if %ERRORLEVEL% NEQ 0 (
    echo [ERROR] Python not found. Install Python and add it to PATH / Python не найден. Установите Python и добавьте его в PATH.
    pause
    exit /b 1
)

echo [INFO] Checking dependencies / Проверяю зависимости...
python -c "import google_auth_oauthlib" >nul 2>&1
if %ERRORLEVEL% NEQ 0 (
    echo [INFO] Installing google-auth-oauthlib / Устанавливаю google-auth-oauthlib...
    pip install google-auth-oauthlib
)

python -c "import dotenv" >nul 2>&1
if %ERRORLEVEL% NEQ 0 (
    echo [INFO] Installing python-dotenv / Устанавливаю python-dotenv...
    pip install python-dotenv
)

echo.
echo [INFO] Starting token generation / Запускаю генерацию токена...
echo.
python "%~dp0generate_refresh_token.py"

echo.
pause
