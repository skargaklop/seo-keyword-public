@echo off
setlocal enabledelayedexpansion

REM Change to execute script from its own directory
cd /d "%~dp0"

echo ===================================================
echo       Auto SEO Keyword Planner Launcher
echo ===================================================

REM 1. Check Python is available
python --version >nul 2>&1
if !ERRORLEVEL! NEQ 0 (
    echo [ERROR] Python is not installed or not in PATH.
    echo [ERROR] Please install Python 3.9+ from https://www.python.org/
    pause
    exit /b 1
)

REM 2. Check and Install Dependencies (check ALL critical modules, not just streamlit)
echo [INFO] Checking dependencies...
python -c "import streamlit; import aiohttp; import trafilatura; import pandas; import openpyxl; import openai; import dotenv; import pydantic; import tenacity; import yaml; import requests; import anthropic; import google.genai" >nul 2>&1
if !ERRORLEVEL! NEQ 0 (
    echo [INFO] Missing dependencies detected. Installing from requirements.txt...
    echo [INFO] This might take a few minutes...
    pip install -r requirements.txt

    if !ERRORLEVEL! NEQ 0 (
        echo [ERROR] Failed to install dependencies. Check your internet connection.
        pause
        exit /b 1
    )
    echo [INFO] Dependencies installed successfully.
) else (
    echo [INFO] All dependencies are installed.
)

REM 3. Run Application
echo.
echo [INFO] Starting Application...
echo.

python -m streamlit run app.py

if !ERRORLEVEL! NEQ 0 (
    echo.
    echo [ERROR] Application execution failed.
    pause
)

endlocal
