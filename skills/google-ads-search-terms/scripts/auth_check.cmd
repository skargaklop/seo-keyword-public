@echo off
setlocal
cd /d "%~dp0"

powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0auth_check.ps1" %*
set "EXIT_CODE=%ERRORLEVEL%"

echo.
if not "%EXIT_CODE%"=="0" (
  echo auth_check.ps1 finished with error code %EXIT_CODE%.
) else (
  echo auth_check.ps1 completed successfully.
)
echo Press any key to close...
pause >nul
exit /b %EXIT_CODE%
