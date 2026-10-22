@echo off
setlocal
cd /d "%~dp0"
title Enable 24/7 Auto-Start: DistributedMesh Worker Node

echo ==============================================================
echo   Enabling 24/7 Auto-Start for DistributedMesh Worker Node
echo   (Zero Admin Rights Required - User Startup)
echo ==============================================================
echo.

set "PROJ_DIR=%~dp0"
set "STARTUP_FOLDER=%APPDATA%\Microsoft\Windows\Start Menu\Programs\Startup"
set "LAUNCHER_VBS=%STARTUP_FOLDER%\DistributedMesh_Worker.vbs"

echo [1/3] Configuring Windows to stay awake even when locked...
powercfg /change standby-timeout-ac 0 >nul 2>nul
powercfg /change hibernate-timeout-ac 0 >nul 2>nul

echo [2/3] Installing background watchdog launcher in Windows Startup folder...
(
echo ' DistributedMesh AI - Silent Autostart Launcher
echo Set WshShell = CreateObject^("WScript.Shell"^)
echo WshShell.CurrentDirectory = "%PROJ_DIR%"
echo WshShell.Run "cmd.exe /c pythonw.exe -m worker.watchdog", 0, False
) > "%LAUNCHER_VBS%"

echo [3/3] Registering in Current User Run registry...
reg add "HKCU\Software\Microsoft\Windows\CurrentVersion\Run" /v "DistributedMeshWorker" /t REG_SZ /d "wscript.exe \"%PROJ_DIR%start_worker_background.vbs\"" /f >nul 2>nul

echo.
echo ==============================================================
echo   [SUCCESS] Auto-Start and Lock-Screen Persistence are ACTIVE!
echo.
echo   • Even if you exit all windows, the worker runs in background.
echo   • Even when your PC is locked (Win + L), it stays connected.
echo   • Screen will turn off to save power, but CPU/network stay on.
echo   • On PC restart or power recovery, it starts automatically.
echo.
echo   To disable later, run: disable_autostart.bat
echo ==============================================================
echo.
if "%1"=="" pause
