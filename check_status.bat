@echo off
setlocal
title DistributedMesh - Local Background Status

echo ==============================================================
echo   Checking DistributedMesh Background Status
echo ==============================================================
echo.

powershell -Command "
$procs = Get-CimInstance Win32_Process | Where-Object { $_.CommandLine -like '*worker.worker_node*' -or $_.CommandLine -like '*worker.watchdog*' }
if ($procs) {
    Write-Host '  [STATUS: ACTIVE]' -ForegroundColor Green
    foreach ($p in $procs) {
        $memMB = [math]::Round((Get-Process -Id $p.ProcessId -ErrorAction SilentlyContinue).WorkingSet64 / 1MB, 1)
        Write-Host ('  • Process: PID ' + $p.ProcessId + ' | Memory WorkingSet: ' + $memMB + ' MB') -ForegroundColor White
    }
} else {
    Write-Host '  [STATUS: STOPPED] No worker processes currently running in background.' -ForegroundColor Yellow
}
"

echo.
if exist "%~dp0logs\worker.log" (
    echo Recent Background Log (Last 10 lines):
    echo --------------------------------------------------------------
    powershell -Command "Get-Content '%~dp0logs\worker.log' -Tail 10"
    echo --------------------------------------------------------------
)

echo.
pause
