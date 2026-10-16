@echo off
setlocal
cd /d "%~dp0"
title GyanSutr - Sovereign AI Launcher
echo ===================================================
echo   GyanSutr - Sovereign Unified Trusted Retrieval
echo ===================================================

where python >nul 2>nul
if %errorlevel% neq 0 (
    echo [ERROR] Python is not installed or not in PATH.
    echo Download Python 3.10+ from https://www.python.org/downloads/
    pause
    exit /b 1
)

if not exist "venv\Scripts\python.exe" (
    echo [1/4] Creating local virtual environment...
    python -m venv venv
)

echo [2/4] Activating environment and checking dependencies...
"venv\Scripts\python.exe" -m pip install --upgrade pip -q
"venv\Scripts\python.exe" -m pip install -r requirements.txt -q

echo [3/4] Checking Ollama models...
where ollama >nul 2>nul
if %errorlevel% equ 0 (
    ollama pull nomic-embed-text
    ollama pull qwen2.5:1.5b
) else (
    echo [WARNING] Ollama not found in PATH. Install from https://ollama.com
)

echo [4/4] Launching GyanSutr...
"venv\Scripts\python.exe" run_app.py
pause