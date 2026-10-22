@echo off
setlocal
title Enable Auto-Start: DistributedMesh Worker Node

echo ==============================================================
echo   Enabling Auto-Start for DistributedMesh Worker Node
echo   (Zero Admin Rights Required - User Startup)
echo ==============================================================
echo.

set "PROJ_DIR=%~dp0"
set "STARTUP_FOLDER=%APPDATA%\Microsoft\Windows\Start Menu\Programs\Startup"
set "LAUNCHER_VBS=%STARTUP_FOLDER%\DistributedMesh_Worker.vbs"

echo [1/2] Installing silent background watchdog launcher in Windows Startup folder...
copy /y "%PROJ_DIR%start_worker_background.vbs" "%LAUNCHER_VBS%" >nul

echo [2/2] Registering in Current User Run registry...
reg add "HKCU\Software\Microsoft\Windows\CurrentVersion\Run" /v "DistributedMeshWorker" /t REG_SZ /d "wscript.exe \"%LAUNCHER_VBS%\"" /f >nul 2>nul

echo.
echo ==============================================================
echo   [SUCCESS] Auto-Start is now ACTIVE!
echo.
echo   Whenever this PC powers on or restarts (e.g. after a power
echo   outage or when electricity returns), the worker node will
echo   start automatically in the background and connect to the
echo   Coordinator and your laptop.
echo.
echo   To disable later, run: disable_autostart.bat
echo ==============================================================
echo.
if "%1"=="" pause
