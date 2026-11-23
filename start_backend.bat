@echo off
setlocal EnableExtensions
title SmartClean AI - Backend (FastAPI)
cd /d "%~dp0backend"

echo ============================================================
echo   SmartClean AI - Backend Bootstrap
echo ============================================================

if not exist "venv\Scripts\python.exe" (
    echo [1/2] Creating isolated virtual environment...
    where py >nul 2>nul
    if errorlevel 1 (
        python -m venv venv
    ) else (
        py -3 -m venv venv
    )
    if errorlevel 1 (
        echo [ERROR] Failed to create venv. Please install Python 3.10+ and retry.
        pause
        exit /b 1
    )
)

venv\Scripts\python.exe -c "import fastapi, pandas, uvicorn, openpyxl, multipart" >nul 2>nul
if errorlevel 1 (
    echo [2/2] Installing Python dependencies from Tsinghua mirror...
    venv\Scripts\python.exe -m pip install -r requirements.txt -i https://pypi.tuna.tsinghua.edu.cn/simple --disable-pip-version-check
    if errorlevel 1 (
        echo [ERROR] Dependency installation failed. Check your network and retry.
        pause
        exit /b 1
    )
)

echo.
echo   API Docs : http://127.0.0.1:8000/docs
echo   Health   : http://127.0.0.1:8000/api/health
echo   Press Ctrl+C to stop this service.
echo.
venv\Scripts\python.exe -m uvicorn app.main:app --host 127.0.0.1 --port 8000 --reload
pause
