@echo off
setlocal
title Launching Background Worker Node

wscript.exe "%~dp0start_worker_background.vbs"

echo ==============================================================
echo   DistributedMesh Worker Node Launched in Background!
echo ==============================================================
echo   • Window: None (Running completely invisible in background)
echo   • Logging: logs\worker.log
echo   • Check Status: check_status.bat
echo   • Stop Worker:  stop_worker.bat
echo ==============================================================
timeout /t 3 /nobreak >nul
