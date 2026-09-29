@echo off
title Huiyan Medical Platform (Port 8000)
cd /d "%~dp0backend"

set "JAVA_HOME=%~dp0jdk-17"
set "PATH=%~dp0jdk-17\bin;%~dp0maven\bin;%PATH%"

echo ========================================================
echo   Huiyan Medical AI Platform (Integrated Single Service)
echo   URL: http://localhost:8000
echo ========================================================
echo.
echo [1/2] Service is starting up...
echo [2/2] Browser will automatically open in 5 seconds.
echo [Info] To stop the platform, just CLOSE THIS WINDOW.
echo.
start /b "" cmd /c "timeout /t 5 /nobreak >nul && start http://localhost:8000"

"%~dp0jdk-17\bin\java.exe" -jar "target\huiyan-backend-1.0.0.jar"

if errorlevel 1 (
    echo.
    echo [Error] Service terminated unexpectedly!
    pause
)
