@echo off
setlocal
cd /d "%~dp0"
title DistributedMesh - Background Worker Status

echo ==============================================================
echo   Checking DistributedMesh Background Status
echo ==============================================================
echo.

python -m worker.status_checker

echo.
if exist "%~dp0logs\worker.log" (
    echo Recent Background Log:
    echo --------------------------------------------------------------
    powershell -NoProfile -Command "Get-Content '%~dp0logs\worker.log' -Tail 8 -ErrorAction SilentlyContinue"
    echo --------------------------------------------------------------
)

echo.
pause
