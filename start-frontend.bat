@echo off
title Huiyan Vue Frontend (Port 5174)
cd /d "%~dp0frontend"

echo ========================================================
echo   Huiyan Medical Platform - Vue Frontend (Port 5174)
echo ========================================================
echo.

if not exist "node_modules" (
    echo [Info] Installing frontend dependencies...
    call npm install
)

echo [Info] Starting Vite Frontend Server on http://localhost:5174 ...
echo [Info] Close this window to stop the frontend.
echo.
call npm run dev

echo.
echo [Notice] Frontend server stopped.
pause
