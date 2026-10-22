@echo off
setlocal
cd /d "%~dp0"
title Launching Background Worker Node

echo [1/3] Terminating any previous worker instances...
if exist "worker.pid" (
    set /p WPID=<"worker.pid"
    if not "%WPID%"=="" taskkill /PID %WPID% /F /T >nul 2>nul
    del "worker.pid" >nul 2>nul
)
powershell -NoProfile -Command "Get-CimInstance Win32_Process | Where-Object { $_.CommandLine -like '*worker.worker_node*' -or $_.CommandLine -like '*worker.watchdog*' } | ForEach-Object { Stop-Process -Id $_.ProcessId -Force -ErrorAction SilentlyContinue }" >nul 2>nul

echo [2/3] Configuring Windows sleep prevention (keeps active when locked)...
powercfg /change standby-timeout-ac 0 >nul 2>nul
powercfg /change hibernate-timeout-ac 0 >nul 2>nul

echo [3/3] Launching silent background worker...
wscript.exe "%~dp0start_worker_background.vbs"

echo ==============================================================
echo   DistributedMesh Worker Node Launched in Background!
echo ==============================================================
echo   • Window: None (Running completely invisible in background)
echo   • Persistence: Stays awake 24/7 even when locked (Win + L)
echo   • Logging: logs\worker.log
echo   • Check Status: check_status.bat
echo   • Stop Worker:  stop_worker.bat
echo ==============================================================
timeout /t 3 /nobreak >nul
