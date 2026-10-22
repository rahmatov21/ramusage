@echo off
setlocal
title Enable Auto-Start: DistributedMesh Master Coordinator

echo ==============================================================
echo   Enabling Auto-Start for DistributedMesh Coordinator Node
echo   (Zero Admin Rights Required - User Startup)
echo ==============================================================
echo.

set "PROJ_DIR=%~dp0"
set "STARTUP_FOLDER=%APPDATA%\Microsoft\Windows\Start Menu\Programs\Startup"
set "LAUNCHER_VBS=%STARTUP_FOLDER%\DistributedMesh_Coordinator.vbs"

echo [1/2] Installing silent background watchdog launcher in Windows Startup folder...
copy /y "%PROJ_DIR%start_coordinator_background.vbs" "%LAUNCHER_VBS%" >nul

echo [2/2] Registering in Current User Run registry...
reg add "HKCU\Software\Microsoft\Windows\CurrentVersion\Run" /v "DistributedMeshCoordinator" /t REG_SZ /d "wscript.exe \"%LAUNCHER_VBS%\"" /f >nul 2>nul

echo.
echo ==============================================================
echo   [SUCCESS] Coordinator Auto-Start is now ACTIVE!
echo.
echo   Whenever this PC powers on or restarts, the Coordinator &
echo   Telegram Bot will start automatically in the background.
echo.
echo   To disable later, run: disable_autostart.bat
echo ==============================================================
echo.
if "%1"=="" pause
