@echo off
setlocal
title Installing DistributedMesh AI (Zero Admin)

echo ==============================================================
echo   Installing DistributedMesh AI (No Admin Rights Needed)
echo ==============================================================
echo.

where python >nul 2>nul
if %ERRORLEVEL% neq 0 (
    echo [ERROR] Python is not found in your PATH.
    echo Please ensure Python 3.10+ is installed on this machine.
    pause
    exit /b 1
)

echo [1/2] Checking Python version...
python --version

echo.
echo [2/2] Installing dependencies into user directory (no admin needed)...
python -m pip install -r requirements.txt --user --no-warn-script-location

if %ERRORLEVEL% neq 0 (
    echo [WARN] User-mode pip failed, trying standard pip install...
    python -m pip install -r requirements.txt
)

echo.
echo ==============================================================
echo   Auto-Start on Boot (Power Outage / Reboot Recovery)
echo ==============================================================
echo   Do you want this PC to automatically launch on boot?
echo   [1] Enable as Worker Node (Recommended for LAN PCs)
echo   [2] Enable as Master Coordinator (For the central PC)
echo   [3] Skip for now (Manual startup only)
echo.
set /p AUTO_CHOICE="Select an option [1, 2, or 3]: "

if "%AUTO_CHOICE%"=="1" (
    call "%~dp0enable_autostart_worker.bat" silent
) else if "%AUTO_CHOICE%"=="2" (
    call "%~dp0enable_autostart_coordinator.bat" silent
) else (
    echo.
    echo [INFO] Auto-start skipped. You can enable it later using:
    echo        enable_autostart_worker.bat or enable_autostart_coordinator.bat
)

echo.
echo ==============================================================
echo   All Setup Completed Successfully!
echo   To start coordinator:  start_coordinator.bat
echo   To start worker node:  start_worker.bat
echo ==============================================================
echo.
pause
