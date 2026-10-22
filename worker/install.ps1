# DistributedMesh AI - Zero-Admin PowerShell Installer
Write-Host "==============================================================" -ForegroundColor Cyan
Write-Host "  Installing DistributedMesh AI (Zero Admin Rights)" -ForegroundColor Cyan
Write-Host "==============================================================" -ForegroundColor Cyan
Write-Host ""

$pythonCmd = Get-Command python -ErrorAction SilentlyContinue
if (-not $pythonCmd) {
    Write-Host "[ERROR] Python was not found in PATH." -ForegroundColor Red
    Write-Host "Please ensure Python 3.10+ is installed." -ForegroundColor Yellow
    exit 1
}

Write-Host "[1/2] Checking Python..." -ForegroundColor Green
python --version

Write-Host ""
Write-Host "[2/2] Installing requirements into current user profile..." -ForegroundColor Green
python -m pip install -r requirements.txt --user --no-warn-script-location

if ($LASTEXITCODE -eq 0) {
    Write-Host ""
    Write-Host "==============================================================" -ForegroundColor Green
    Write-Host "  Dependencies Installed Successfully!" -ForegroundColor Green
    Write-Host "==============================================================" -ForegroundColor Green
    Write-Host ""
    Write-Host "Auto-Start Configuration (Power Outage / Reboot Recovery):" -ForegroundColor Cyan
    Write-Host "  [1] Enable as Worker Node (Recommended for LAN PCs)"
    Write-Host "  [2] Enable as Master Coordinator (For the central PC)"
    Write-Host "  [3] Skip for now (Manual startup only)"
    $choice = Read-Host "Select an option [1, 2, or 3]"
    if ($choice -eq "1") {
        & "$PSScriptRoot\enable_autostart_worker.bat" silent
    } elseif ($choice -eq "2") {
        & "$PSScriptRoot\enable_autostart_coordinator.bat" silent
    } else {
        Write-Host "[INFO] Auto-start skipped. You can enable it anytime via enable_autostart_worker.bat" -ForegroundColor Yellow
    }

    Write-Host ""
    Write-Host "==============================================================" -ForegroundColor Green
    Write-Host "  Setup Complete!" -ForegroundColor Green
    Write-Host "  Coordinator Node: .\start_coordinator.bat" -ForegroundColor White
    Write-Host "  Worker Node:      .\start_worker.bat" -ForegroundColor White
    Write-Host "==============================================================" -ForegroundColor Green
} else {
    Write-Host "[WARN] Pip encountered an issue. Please review above logs." -ForegroundColor Yellow
}
