@echo off
setlocal
cd /d "%~dp0"
title DistributedMesh AI - Stop Worker

echo ==============================================================
echo   Stopping DistributedMesh Worker Node
echo ==============================================================
echo.

:: 1. Terminate watchdog using PID if available
if exist "%~dp0worker.pid" (
    set /p WPID=<"%~dp0worker.pid"
    if not "%WPID%"=="" (
        echo [1/4] Terminating background supervisor (PID %WPID%)...
        taskkill /PID %WPID% /F /T >nul 2>nul
        del /f /q "%~dp0worker.pid" >nul 2>nul
    )
)

:: 2. Terminate all worker and watchdog python processes
echo [2/4] Terminating any worker and watchdog processes...
powershell -NoProfile -Command "Get-CimInstance Win32_Process | Where-Object { $_.CommandLine -like '*worker.worker_node*' -or $_.CommandLine -like '*worker.watchdog*' } | ForEach-Object { Stop-Process -Id $_.ProcessId -Force -ErrorAction SilentlyContinue }" >nul 2>nul

:: 3. Remove Windows auto-start entries
echo [3/4] Removing Windows startup auto-run entries...
set "STARTUP_FOLDER=%APPDATA%\Microsoft\Windows\Start Menu\Programs\Startup"
if exist "%STARTUP_FOLDER%\DistributedMesh_Worker.vbs" (
    del /f /q "%STARTUP_FOLDER%\DistributedMesh_Worker.vbs" >nul 2>nul
)
reg delete "HKCU\Software\Microsoft\Windows\CurrentVersion\Run" /v "DistributedMeshWorker" /f >nul 2>nul

:: 4. Restore default Windows power sleep timeout (30 min)
echo [4/4] Restoring default Windows sleep settings...
powercfg /change standby-timeout-ac 30 >nul 2>nul
powercfg /change hibernate-timeout-ac 0 >nul 2>nul

echo.
echo ==============================================================
echo   [SUCCESS] Worker has been COMPLETELY STOPPED!
echo ==============================================================
echo   • Worker processes: Terminated
echo   • Port 8501: Released
echo   • Windows Autostart: Disabled
echo   • Normal Sleep: Restored
echo.
echo   To start again in foreground: double-click start.bat
echo   To start 24/7 in background:  double-click run_forever.bat
echo ==============================================================
echo.
if "%1"=="" pause
