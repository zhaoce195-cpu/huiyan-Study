@echo off
title Stop Huiyan Services
echo ========================================================
echo   Stopping Huiyan Platform Services...
echo ========================================================
echo.
powershell -NoProfile -Command "Get-NetTCPConnection -LocalPort 8000,5174 -ErrorAction SilentlyContinue | ForEach-Object { Stop-Process -Id $_.OwningProcess -Force -ErrorAction SilentlyContinue }"
echo [OK] All Huiyan services have been stopped.
timeout /t 2 >nul
