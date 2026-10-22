# DistributedMesh AI - Remote Worker 1-Click Installer
# Host: https://ramusageailaptop.netlify.app
param(
    [string]$Origin = "https://ramusageailaptop.netlify.app",
    [string]$Coordinator = ""
)

$ErrorActionPreference = "Stop"
Write-Host ""
Write-Host "==============================================================" -ForegroundColor Cyan
Write-Host "   🧠 DistributedMesh AI - RAM Worker Node Installer" -ForegroundColor Green
Write-Host "   Zero-Admin, Invisible Background Node for Windows" -ForegroundColor Gray
Write-Host "==============================================================" -ForegroundColor Cyan
Write-Host ""

# 1. Resolve Origin
if (-not $Origin -and $env:MESH_ORIGIN) {
    $Origin = $env:MESH_ORIGIN
}
if (-not $Origin) {
    $invFile = $MyInvocation.MyCommand.ScriptBlock.File
    if ($invFile -and $invFile.StartsWith("http")) {
        $Uri = [System.Uri]$invFile
        $Origin = "$($Uri.Scheme)://$($Uri.Authority)"
    }
}
if (-not $Origin) {
    $Origin = "https://ramusageailaptop.netlify.app"
}

$Origin = $Origin.Trim().TrimEnd('/')
$ZipUrl = "$Origin/worker.zip"

# 2. Target directory in user profile (Zero Admin)
$TargetDir = Join-Path $env:USERPROFILE "DistributedMeshWorker"

# 3. Prompt for Coordinator endpoint if not provided
if (-not $Coordinator) {
    Write-Host "Enter Coordinator URL (or press Enter for permanent cloud server):" -ForegroundColor Yellow
    $DefaultCoord = "https://ramusage-3656d30fbed9.herokuapp.com"
    $InputCoord = Read-Host "Coordinator URL [$DefaultCoord]"
    if ([string]::IsNullOrWhiteSpace($InputCoord)) {
        $Coordinator = $DefaultCoord
    } else {
        $Coordinator = $InputCoord.Trim()
    }
}

if (-not $Coordinator.StartsWith("http")) {
    $Coordinator = "http://$Coordinator"
}

Write-Host "`n[*] Downloading worker bundle from: $ZipUrl" -ForegroundColor Gray
Write-Host "[*] Target installation folder:     $TargetDir" -ForegroundColor Gray
Write-Host "[*] Coordinator endpoint:           $Coordinator" -ForegroundColor Cyan

if (-not (Test-Path $TargetDir)) {
    New-Item -ItemType Directory -Path $TargetDir -Force | Out-Null
}

# 4. Download worker.zip
$ZipDest = Join-Path $env:TEMP "mesh_worker.zip"
Write-Host "[*] Downloading package..." -ForegroundColor Gray

try {
    Invoke-WebRequest -Uri $ZipUrl -OutFile $ZipDest -UseBasicParsing
} catch {
    Write-Host "[!] Retrying with Invoke-RestMethod..." -ForegroundColor Yellow
    Invoke-RestMethod -Uri $ZipUrl -OutFile $ZipDest
}

Write-Host "[*] Extracting package into $TargetDir..." -ForegroundColor Gray
Expand-Archive -Path $ZipDest -DestinationPath $TargetDir -Force
Remove-Item -Path $ZipDest -Force -ErrorAction SilentlyContinue

# 5. Update config.json with specified coordinator
$ConfigFile = Join-Path $TargetDir "config.json"
if (Test-Path $ConfigFile) {
    try {
        $Config = Get-Content $ConfigFile -Raw | ConvertFrom-Json
        $Config.worker.coordinator_url = $Coordinator
        $Config | ConvertTo-Json -Depth 10 | Set-Content $ConfigFile -Encoding UTF8
    } catch {
        Write-Warning "Could not update config.json directly, fallback to command line argument."
    }
}

# 6. Install dependencies in user mode
Write-Host "[*] Verifying Python and installing dependencies (User-Space, Zero Admin)..." -ForegroundColor Gray
$pythonCmd = (Get-Command python -ErrorAction SilentlyContinue).Source
if (-not $pythonCmd) {
    Write-Host "[ERROR] Python 3 was not found in PATH! Please install Python 3.9+ and try again." -ForegroundColor Red
    return
}

$reqFile = Join-Path $TargetDir "requirements.txt"
& python -m pip install -r $reqFile --user --quiet --no-warn-script-location

# 7. Setup auto-start in HKCU\Software\Microsoft\Windows\CurrentVersion\Run
Write-Host "[*] Configuring 24/7 background autostart on system boot..." -ForegroundColor Gray
$vbsPath = Join-Path $TargetDir "start_worker_background.vbs"
$regKey = "HKCU:\Software\Microsoft\Windows\CurrentVersion\Run"
$regValue = "wscript.exe `"$vbsPath`""
Set-ItemProperty -Path $regKey -Name "DistributedMeshWorker" -Value $regValue -Force

# 8. Stop any previous worker processes first (in case of re-join)
& cmd.exe /c "taskkill /F /FI ""COMMANDLINE like *worker.worker_node*"" >nul 2>&1"
& cmd.exe /c "taskkill /F /FI ""COMMANDLINE like *worker.watchdog*"" >nul 2>&1"
Start-Sleep -Milliseconds 800

# 9. Launch the worker invisibly right now
Write-Host "[*] Launching invisible background worker..." -ForegroundColor Green
Start-Process -FilePath "wscript.exe" -ArgumentList "`"$vbsPath`"" -WorkingDirectory $TargetDir

Write-Host ""
Write-Host "==============================================================" -ForegroundColor Green
Write-Host "   [SUCCESS] Worker is now active and providing RAM!" -ForegroundColor Green
Write-Host "   - Status:      Running 100% in background (zero windows)" -ForegroundColor White
Write-Host "   - Coordinator: $Coordinator" -ForegroundColor White
Write-Host "   - Auto-start:  Enabled (restarts automatically on reboot)" -ForegroundColor White
Write-Host "==============================================================" -ForegroundColor Green
Write-Host ""
