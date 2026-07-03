@echo off
chcp 65001 >nul
setlocal EnableExtensions DisableDelayedExpansion
cd /d "%~dp0"

echo Looking for Python 3 (global interpreter)...

set "PYTHON_EXE="
set "PYTHON_ARGS="

where py.exe >nul 2>&1
if %errorlevel%==0 (
  py -3 -c "import sys; raise SystemExit(0 if sys.version_info[0] == 3 else 1)" >nul 2>&1
  if %errorlevel%==0 (
    set "PYTHON_EXE=py"
    set "PYTHON_ARGS=-3"
    goto :python_found
  )
)

for %%V in (314 313 312 311 310 39 38) do (
  for %%F in ("%LOCALAPPDATA%\Programs\Python\Python%%V\python.exe" "C:\Program Files\Python%%V\python.exe" "C:\Python%%V\python.exe") do (
    if exist "%%~F" (
      "%%~F" -c "import sys; raise SystemExit(0 if sys.version_info[0] == 3 else 1)" >nul 2>&1
      if not errorlevel 1 (
        set "PYTHON_EXE=%%~F"
        goto :python_found
      )
    )
  )
)

for /f "delims=" %%P in ('where python.exe 2^>nul ^| findstr /i /v "\\WindowsApps\\"') do (
  echo %%~fP | findstr /i "\\.venv\\" >nul
  if errorlevel 1 (
    "%%~fP" -c "import sys; raise SystemExit(0 if sys.version_info[0] == 3 else 1)" >nul 2>&1
    if not errorlevel 1 (
      set "PYTHON_EXE=%%~fP"
      goto :python_found
    )
  )
)

python -c "import sys; raise SystemExit(0 if sys.version_info[0] == 3 else 1)" >nul 2>&1
if %errorlevel%==0 (
  set "PYTHON_EXE=python"
  goto :python_found
)

echo ERROR: Python 3 not found.
echo Install Python from python.org and rerun this script.
echo.
pause
exit /b 1

:python_found
echo Python found: %PYTHON_EXE% %PYTHON_ARGS%
"%PYTHON_EXE%" %PYTHON_ARGS% --version
if errorlevel 1 (
  echo ERROR: Failed to run detected Python interpreter.
  echo.
  pause
  exit /b 1
)

if not exist "requirements.txt" (
  echo ERROR: requirements.txt not found in %cd%
  echo.
  pause
  exit /b 1
)

"%PYTHON_EXE%" %PYTHON_ARGS% -m pip --version >nul 2>&1
if errorlevel 1 (
  echo pip is missing. Trying to bootstrap with ensurepip...
  "%PYTHON_EXE%" %PYTHON_ARGS% -m ensurepip --upgrade
  if errorlevel 1 (
    echo ERROR: Could not bootstrap pip.
    echo.
    pause
    exit /b 1
  )
)

echo.
echo Upgrading pip...
"%PYTHON_EXE%" %PYTHON_ARGS% -m pip install --upgrade pip
if errorlevel 1 (
  echo ERROR: Failed to upgrade pip.
  echo.
  pause
  exit /b 1
)

echo.
echo Installing dependencies globally from requirements.txt...
"%PYTHON_EXE%" %PYTHON_ARGS% -m pip install -r requirements.txt
set "EXIT_CODE=%errorlevel%"

if not "%EXIT_CODE%"=="0" (
  echo.
  echo Installation failed with exit code: %EXIT_CODE%
  echo If you see access errors, run this .bat as Administrator.
  echo.
  pause
  endlocal
  exit /b %EXIT_CODE%
)

echo.
echo Done: dependencies installed globally.
echo.
pause
endlocal
exit /b 0
