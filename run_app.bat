@echo off
setlocal enabledelayedexpansion

REM Auto SEO Keyword Planner - Launcher (runs the Streamlit UI only).
REM NO dependency work here - run install_app.bat ONCE first.
REM Uses the project-local .venv if install_app.bat created one; otherwise
REM discovers a global Python via the same 4-tier chain as the installer.
REM Forwards all arguments to `streamlit run app.py` (e.g. --server.port 8502).

cd /d "%~dp0"

chcp 65001 > nul
set "PYTHONUTF8=1"

echo ===================================================
echo       Auto SEO Keyword Planner Launch / Запуск Auto SEO Keyword Planner
echo ===================================================
echo.

REM ------------------------------------------------------------------
REM Python selection: prefer a project venv if it exists, else discover.
REM The venv path matches the one install_app.bat creates (.venv\Scripts).
REM ------------------------------------------------------------------
set "PYTHON_CMD="

if exist ".venv\Scripts\python.exe" (
  set "PYTHON_CMD=.venv\Scripts\python.exe"
  echo [INFO] Using project venv: .venv / Используется виртуальное окружение проекта: .venv
  goto :python_found
)

REM Tier 1: bare `python` on PATH, real Python 3 only (not the Store stub).
python --version >nul 2>&1
if !errorlevel!==0 (
  for /f "tokens=2 delims= " %%V in ('python --version 2^>^&1') do (
    echo %%V | findstr /r "^3\." >nul && (
      set "PYTHON_CMD=python"
      goto :python_found
    )
  )
)

REM Tier 2: official `py` launcher (py -3).
where py.exe >nul 2>&1
if !errorlevel!==0 (
  py -3 -c "import sys" >nul 2>&1
  if !errorlevel!==0 (
    set "PYTHON_CMD=py -3"
    goto :python_found
  )
)

REM Tier 3: any python.exe on PATH that is NOT the WindowsApps Store stub.
for /f "delims=" %%P in ('where python.exe 2^>nul ^| findstr /i /v "WindowsApps"') do (
  "%%~fP" --version >nul 2>&1
  if !errorlevel!==0 (
    set "PYTHON_CMD=%%~fP"
    goto :python_found
  )
)

REM Tier 4: probe common install locations, versions 3.14 down to 3.8.
for %%V in (314 313 312 311 310 39 38) do (
  for %%F in ("%LOCALAPPDATA%\Programs\Python\Python%%V\python.exe" "C:\Program Files\Python%%V\python.exe" "C:\Python%%V\python.exe") do (
    if exist "%%~F" (
      set "PYTHON_CMD=%%~F"
      goto :python_found
    )
  )
)

REM All tiers failed.
echo [ERROR]  Python 3 was not found in PATH or any standard location / Python 3 не найден ни в PATH, ни в стандартных расположениях.
echo           The Microsoft Store stub does not count / Заглушка Microsoft Store не подходит.
echo           Install Python 3.10+ from https://www.python.org/ / Установите Python 3.10+ с https://www.python.org/
echo           Tick "Add Python to PATH" during install / Отметьте "Add Python to PATH" во время установки.
echo.
echo           Or run install_app.bat first to set up dependencies and a venv / Или сначала запустите install_app.bat для установки зависимостей и .venv.
pause
exit /b 1

:python_found
echo [INFO] Starting application / Запуск приложения...
echo.

"!PYTHON_CMD!" -m streamlit run app.py %*
set "RC=!errorlevel!"

if "!RC!" NEQ "0" (
  echo.
  echo [ERROR]  Application execution failed, rc=!RC! / Ошибка запуска приложения, код !RC!.
  pause
)

exit /b !RC!
