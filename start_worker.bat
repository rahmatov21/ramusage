@echo off
setlocal
cd /d "%~dp0"
title DistributedMesh AI - Worker Node Agent
set PYTHONUNBUFFERED=1

echo ==============================================================
echo   Starting Worker Node Agent and Keep-Alive Watchdog
echo   (Continuous 24/7 persistence - Zero Admin Rights Required)
echo.
echo   TIP: To run headless with ZERO windows and stay alive
echo   even after locking your PC (Win + L), use: run_forever.bat
echo ==============================================================
echo.

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
:watchdog_loop
%PY_CMD% -m worker.worker_node %*

echo.
echo ==============================================================
echo   [WATCHDOG] Worker process stopped at %DATE% %TIME%
echo   [WATCHDOG] Automatically restarting in 2 seconds...
echo   (Press Ctrl+C to terminate)
echo ==============================================================
timeout /t 2 /nobreak >nul
goto watchdog_loop
