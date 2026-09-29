@echo off
title Huiyan Java Backend (Port 8000)
cd /d "%~dp0backend"

set "JAVA_HOME=%~dp0jdk-17"
set "PATH=%~dp0jdk-17\bin;%~dp0maven\bin;%PATH%"

echo ========================================================
echo   Huiyan Medical Platform - Java Backend (Port 8000)
echo ========================================================
echo.

if not exist "target\huiyan-backend-1.0.0.jar" (
    echo [Info] Target jar not found. Building with Maven...
    call "%~dp0maven\bin\mvn.cmd" clean package -DskipTests
    if errorlevel 1 (
        echo.
        echo [Error] Maven build failed!
        pause
        exit /b 1
    )
)

echo [Info] Starting Spring Boot Backend on http://localhost:8000 ...
echo [Info] SQLite Database: backend/edu_eye.db
echo [Info] Close this window to stop the backend.
echo.
"%~dp0jdk-17\bin\java.exe" -jar "target\huiyan-backend-1.0.0.jar"

if errorlevel 1 (
    echo.
    echo [Error] Backend exited unexpectedly!
    pause
)
