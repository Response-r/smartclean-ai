@echo off
setlocal EnableExtensions
title SmartClean AI - Frontend (Vite)
cd /d "%~dp0frontend"

echo ============================================================
echo   SmartClean AI - Frontend Bootstrap
echo ============================================================

where node >nul 2>nul
if errorlevel 1 (
    echo [ERROR] Node.js is not installed or not in PATH. Please install Node.js 18+.
    pause
    exit /b 1
)

if not exist "node_modules" (
    echo [1/1] Installing frontend dependencies from npmmirror...
    call npm install --registry=https://registry.npmmirror.com --no-audit --no-fund
    if errorlevel 1 (
        echo [ERROR] npm install failed. Check your network and retry.
        pause
        exit /b 1
    )
)

echo.
echo   Dashboard: http://127.0.0.1:5173
echo   Backend  : http://127.0.0.1:8000  (run start_backend.bat first)
echo   Press Ctrl+C to stop this service.
echo.
call npm run dev
pause
