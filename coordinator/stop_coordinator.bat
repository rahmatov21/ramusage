@echo off
setlocal
title Stopping Coordinator Node

echo ==============================================================
echo   Stopping DistributedMesh Coordinator
echo ==============================================================
echo.

if exist "%~dp0coordinator.pid" (
    del /f /q "%~dp0coordinator.pid" >nul 2>&1
)

echo [INFO] Terminating coordinator processes...
taskkill /F /FI "COMMANDLINE like *coordinator.coordinator*" >nul 2>&1
taskkill /F /FI "COMMANDLINE like *start_coordinator*" >nul 2>&1

echo.
echo ==============================================================
echo   [SUCCESS] Coordinator has been completely stopped.
echo ==============================================================
echo.
if "%1"=="" pause
