@echo off
setlocal
title Stopping Background Worker Node

echo ==============================================================
echo   Stopping DistributedMesh Background Worker
echo ==============================================================
echo.

if exist "%~dp0worker.pid" (
    set /p WPID=<"%~dp0worker.pid"
    if not "%WPID%"=="" (
        echo [INFO] Terminating background watchdog (PID %WPID%)...
        taskkill /PID %WPID% /F /T >nul 2>nul
        del "%~dp0worker.pid" >nul 2>nul
    )
)

echo [INFO] Terminating any lingering worker processes...
powershell -Command "Get-CimInstance Win32_Process | Where-Object { $_.CommandLine -like '*worker.worker_node*' -or $_.CommandLine -like '*worker.watchdog*' } | ForEach-Object { Stop-Process -Id $_.ProcessId -Force -ErrorAction SilentlyContinue }" >nul 2>nul

echo.
echo ==============================================================
echo   [SUCCESS] Background worker has been completely stopped.
echo ==============================================================
echo.
if "%1"=="" pause
