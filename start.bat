@echo off
setlocal
cd /d "%~dp0"
title DistributedMesh AI - Worker Node Agent
set PYTHONUNBUFFERED=1

echo ==============================================================
echo   Starting DistributedMesh Worker Node (Foreground Mode)
echo ==============================================================
echo.

:: Stop any conflicting worker processes first
powershell -NoProfile -Command "Get-CimInstance Win32_Process | Where-Object { $_.CommandLine -like '*worker.worker_node*' -or $_.CommandLine -like '*worker.watchdog*' } | ForEach-Object { Stop-Process -Id $_.ProcessId -Force -ErrorAction SilentlyContinue }" >nul 2>nul
if exist "worker.pid" del /f /q "worker.pid" >nul 2>nul

:: Detect Python executable in PATH
where python >nul 2>&1
if %ERRORLEVEL% EQU 0 (
    set "PY_CMD=python"
    goto :found_python
)

where py >nul 2>&1
if %ERRORLEVEL% EQU 0 (
    set "PY_CMD=py -3"
    goto :found_python
)

echo [ERROR] Python 3 was not found in PATH!
echo Please install Python 3.9+ and ensure "Add python to PATH" is checked during setup.
echo.
pause
exit /b 1

:found_python
:: Verify and auto-install dependencies if missing (zero admin)
%PY_CMD% -c "import fastapi, uvicorn, psutil, requests, pydantic" >nul 2>&1
if %ERRORLEVEL% NEQ 0 (
    echo [INFO] First-time setup: Installing required libraries...
    %PY_CMD% -m pip install -r requirements.txt --user --quiet --no-warn-script-location
)

echo [INFO] Running worker in live console mode...
echo (To run silently in background with auto-start instead, use: run_forever.bat)
echo (Press Ctrl+C to stop)
echo.

:watchdog_loop
%PY_CMD% -m worker.worker_node %*

echo.
echo ==============================================================
echo   [WATCHDOG] Worker process stopped at %DATE% %TIME%
echo   [WATCHDOG] Automatically restarting in 2 seconds...
echo   (Press Ctrl+C to terminate)
echo ==============================================================
ping 127.0.0.1 -n 3 >nul
goto watchdog_loop
