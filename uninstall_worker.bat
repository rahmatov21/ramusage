@echo off
title DistributedMesh RAM Worker - Clean Uninstaller
setlocal

echo ==============================================================
echo    DistributedMesh AI - Local Worker Clean Uninstaller
echo ==============================================================
echo.
echo This utility will completely uninstall the DistributedMesh Worker
echo from this PC, remove Windows startup entries, stop all background
echo processes, and delete all application files and logs.
echo.
set /p CONFIRM="Type YES to execute complete uninstallation: "
if /i not "%CONFIRM%"=="YES" (
    echo.
    echo [CANCELED] No changes were made.
    pause
    exit /b 0
)

echo.
echo [*] Removing Windows Registry autostart key...
reg delete "HKCU\Software\Microsoft\Windows\CurrentVersion\Run" /v "DistributedMeshWorker" /f >nul 2>&1

echo [*] Removing Startup folder shortcuts if present...
if exist "%APPDATA%\Microsoft\Windows\Start Menu\Programs\Startup\DistributedMeshWorker.lnk" (
    del /f /q "%APPDATA%\Microsoft\Windows\Start Menu\Programs\Startup\DistributedMeshWorker.lnk" >nul 2>&1
)
if exist "%APPDATA%\Microsoft\Windows\Start Menu\Programs\Startup\start_worker.vbs" (
    del /f /q "%APPDATA%\Microsoft\Windows\Start Menu\Programs\Startup\start_worker.vbs" >nul 2>&1
)

echo [*] Terminating worker and watchdog processes...
taskkill /F /FI "COMMANDLINE like *worker.worker_node*" >nul 2>&1
taskkill /F /FI "COMMANDLINE like *worker.watchdog*" >nul 2>&1
taskkill /F /IM rpc-server.exe >nul 2>&1

echo [*] Cleaning temporary download caches...
if exist "%TEMP%\mesh_worker.zip" del /f /q "%TEMP%\mesh_worker.zip" >nul 2>&1
if exist "%TEMP%\join.ps1" del /f /q "%TEMP%\join.ps1" >nul 2>&1
if exist "%TEMP%\join.bat" del /f /q "%TEMP%\join.bat" >nul 2>&1
if exist "%TEMP%\mesh_code_red.bat" del /f /q "%TEMP%\mesh_code_red.bat" >nul 2>&1

set "TARGET_DIR=%USERPROFILE%\DistributedMeshWorker"
if exist "%TARGET_DIR%" (
    echo [*] Deleting installed files in: %TARGET_DIR%...
    rmdir /S /Q "%TARGET_DIR%" >nul 2>&1
)

echo.
echo ==============================================================
echo    [SUCCESS] Application, services, and logs cleanly removed!
echo    This computer is completely restored to its original state.
echo ==============================================================
echo.
pause
