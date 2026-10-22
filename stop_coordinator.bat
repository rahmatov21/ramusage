@echo off
setlocal
title Stopping Coordinator Node

echo ==============================================================
echo   Stopping DistributedMesh Coordinator
echo ==============================================================
echo.

if exist "%~dp0coordinator.pid" (
    set /p CPID=<"%~dp0coordinator.pid"
    if not "%CPID%"=="" (
        echo [INFO] Terminating coordinator watchdog (PID %CPID%)...
        taskkill /PID %CPID% /F /T >nul 2>nul
        del "%~dp0coordinator.pid" >nul 2>nul
    )
)

echo [INFO] Terminating any lingering coordinator processes...
powershell -Command "Get-CimInstance Win32_Process | Where-Object { $_.CommandLine -like '*coordinator.coordinator*' -or $_.CommandLine -like '*coordinator.watchdog*' } | ForEach-Object { Stop-Process -Id $_.ProcessId -Force -ErrorAction SilentlyContinue }" >nul 2>nul

echo.
echo ==============================================================
echo   [SUCCESS] Coordinator has been completely stopped.
echo ==============================================================
echo.
if "%1"=="" pause
