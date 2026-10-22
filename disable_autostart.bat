@echo off
setlocal
title Disable Auto-Start: DistributedMesh AI

echo ==============================================================
echo   Disabling Auto-Start for DistributedMesh AI
echo ==============================================================
echo.

set "STARTUP_FOLDER=%APPDATA%\Microsoft\Windows\Start Menu\Programs\Startup"

if exist "%STARTUP_FOLDER%\DistributedMesh_Worker.vbs" (
    del "%STARTUP_FOLDER%\DistributedMesh_Worker.vbs"
    echo [OK] Removed Worker from Windows Startup folder.
)

if exist "%STARTUP_FOLDER%\DistributedMesh_Coordinator.vbs" (
    del "%STARTUP_FOLDER%\DistributedMesh_Coordinator.vbs"
    echo [OK] Removed Coordinator from Windows Startup folder.
)

reg delete "HKCU\Software\Microsoft\Windows\CurrentVersion\Run" /v "DistributedMeshWorker" /f >nul 2>nul
reg delete "HKCU\Software\Microsoft\Windows\CurrentVersion\Run" /v "DistributedMeshCoordinator" /f >nul 2>nul
echo [OK] Cleaned Windows CurrentUser Run registry keys.

echo.
echo [SUCCESS] Auto-start has been completely disabled.
echo.
if "%1"=="" pause
