@echo off
title Huiyan Medical Platform - Starter
cd /d "%~dp0"

echo ========================================================
echo   Huiyan Medical Platform (Java Backend + Vue Frontend)
echo ========================================================
echo.

echo [1/3] Starting Java Backend on port 8000...
start "Huiyan Java Backend (Port 8000)" "%~dp0start-backend.bat"

echo Waiting for Backend initialization (5 seconds)...
timeout /t 5 /nobreak >nul

echo [2/3] Starting Vue Frontend on port 5174...
start "Huiyan Vue Frontend (Port 5174)" "%~dp0start-frontend.bat"

echo Waiting for Frontend to initialize (3 seconds)...
timeout /t 3 /nobreak >nul

echo [3/3] Opening browser at http://localhost:5174 ...
start http://localhost:5174

echo.
echo ========================================================
echo   Both services have been launched in separate windows!
echo   Frontend URL: http://localhost:5174
echo   Backend  URL: http://localhost:8000
echo.
echo   Please KEEP the backend and frontend windows running.
echo   Press any key to close this launcher window.
echo ========================================================
echo.
pause
