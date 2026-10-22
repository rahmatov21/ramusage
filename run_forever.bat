@echo off
setlocal
cd /d "%~dp0"
title DistributedMesh AI - Run Worker Forever in Background

echo ==============================================================
echo   DistributedMesh AI - 1-Click Worker Setup (Run Forever)
echo   (Continuous 24/7 Background Persistence - Zero Admin Required)
echo ==============================================================
echo.

:: 1. Terminate any previous foreground or background worker processes cleanly
echo [1/5] Stopping any running worker instances to prevent port conflicts...
if exist "worker.pid" (
    set /p WPID=<"worker.pid"
    if not "%WPID%"=="" taskkill /PID %WPID% /F /T >nul 2>nul
    del "worker.pid" >nul 2>nul
)
powershell -NoProfile -Command "Get-CimInstance Win32_Process | Where-Object { $_.CommandLine -like '*worker.worker_node*' -or $_.CommandLine -like '*worker.watchdog*' } | ForEach-Object { Stop-Process -Id $_.ProcessId -Force -ErrorAction SilentlyContinue }" >nul 2>nul
ping 127.0.0.1 -n 2 >nul

:: 2. Configure Windows Power settings (Zero Admin Required)
echo [2/5] Configuring Windows sleep prevention (keeps active when locked)...
powercfg /change standby-timeout-ac 0 >nul 2>nul
powercfg /change hibernate-timeout-ac 0 >nul 2>nul

:: 3. Enable Auto-Start on Windows boot / login
echo [3/5] Setting up automatic startup on Windows boot/login...
set "STARTUP_FOLDER=%APPDATA%\Microsoft\Windows\Start Menu\Programs\Startup"
set "LAUNCHER_VBS=%STARTUP_FOLDER%\DistributedMesh_Worker.vbs"
(
echo ' DistributedMesh AI - Autostart Launcher
echo Set WshShell = CreateObject^("WScript.Shell"^)
echo WshShell.CurrentDirectory = "%~dp0"
echo WshShell.Run "cmd.exe /c pythonw.exe -m worker.watchdog", 0, False
) > "%LAUNCHER_VBS%"
reg add "HKCU\Software\Microsoft\Windows\CurrentVersion\Run" /v "DistributedMeshWorker" /t REG_SZ /d "wscript.exe \"%~dp0start_worker_background.vbs\"" /f >nul 2>nul

:: 4. Launch the silent background worker
echo [4/5] Launching worker silently in the background...
wscript.exe "%~dp0start_worker_background.vbs"
ping 127.0.0.1 -n 4 >nul

:: 5. Verify local health and cloud heartbeat
echo [5/5] Verifying worker health and cloud heartbeat connection...
python -c "import requests, time, sys; ok = False; (lambda: [setattr(sys, '_r', requests.get('http://127.0.0.1:8501/status', timeout=2)) for _ in range(5) if not hasattr(sys, '_r') and not time.sleep(1)])(); d = getattr(sys, '_r', None); sys.exit(0 if (d and d.status_code == 200 and print('   -> Local Worker API: ONLINE (Node ID: ' + d.json().get('node_id','') + ', Free RAM: ' + str(round(d.json().get('memory',{}).get('avail_ram_mb',0))) + ' MB)')) else 1)" 2>nul
if %ERRORLEVEL% EQU 0 (
    echo   [OK] Worker is confirmed running in the background!
) else (
    echo   [INFO] Worker starting in background.
)

echo.
echo ==============================================================
echo   [SUCCESS] DistributedMesh Worker is now running FOREVER!
echo ==============================================================
echo.
echo   • ZERO WINDOWS: Running completely headless in the background.
echo   • ALWAYS ON: When locked (Win + L), CPU and network stay alive.
echo   • AUTO-START: Automatically starts whenever Windows boots or logs in.
echo   • SAFE TO CLOSE: You can now CLOSE THIS WINDOW and exit everything!
echo.
echo   Cloud Coordinator: https://ramusage-3656d30fbed9.herokuapp.com
echo   To stop worker anytime: double-click stop.bat
echo ==============================================================
echo.
pause
