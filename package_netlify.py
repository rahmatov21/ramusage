#!/usr/bin/env python3
"""
Netlify Deployment Packager for DistributedMesh AI
Builds a production-ready 'netlify_deploy/' directory for ramusageailaptop.netlify.app
"""

import os
import sys
import zipfile
import shutil
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent
OUTPUT_DIR = BASE_DIR / "netlify_deploy"
DEFAULT_NETLIFY_ORIGIN = "https://ramusageailaptop.netlify.app"

def build_worker_zip():
    zip_path = OUTPUT_DIR / "worker.zip"
    print(f"[*] Packaging worker bundle into {zip_path.name}...")

    worker_files = [
        "requirements.txt",
        "start_worker_background.vbs",
        "start_worker_background.bat",
        "stop_worker.bat",
        "check_status.bat",
        "enable_autostart_worker.bat",
        "disable_autostart.bat",
        "uninstall_worker.bat",
    ]

    worker_dirs = [
        "worker",
        "common",
    ]

    with zipfile.ZipFile(zip_path, "w", zipfile.ZIP_DEFLATED) as zf:
        for f in worker_files:
            file_path = BASE_DIR / f
            if file_path.exists():
                zf.write(file_path, arcname=f)

        config_src = BASE_DIR / "config.example.json"
        if not config_src.exists():
            config_src = BASE_DIR / "config.json"
        if config_src.exists():
            zf.write(config_src, arcname="config.json")

        for d in worker_dirs:
            dir_path = BASE_DIR / d
            if dir_path.exists():
                for root, _, files in os.walk(dir_path):
                    for file in files:
                        if not file.endswith((".pyc", ".pyo")) and "__pycache__" not in root:
                            full_path = Path(root) / file
                            rel_path = full_path.relative_to(BASE_DIR)
                            zf.write(full_path, arcname=str(rel_path))

    size_kb = zip_path.stat().st_size / 1024
    print(f"[+] Created {zip_path.name} ({size_kb:.1f} KB)")


def write_join_ps1():
    ps1_content = rf'''# DistributedMesh AI - Remote Worker 1-Click Installer
# Host: {DEFAULT_NETLIFY_ORIGIN}
param(
    [string]$Origin = "{DEFAULT_NETLIFY_ORIGIN}",
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
if (-not $Origin -and $env:MESH_ORIGIN) {{
    $Origin = $env:MESH_ORIGIN
}}
if (-not $Origin) {{
    $invFile = $MyInvocation.MyCommand.ScriptBlock.File
    if ($invFile -and $invFile.StartsWith("http")) {{
        $Uri = [System.Uri]$invFile
        $Origin = "$($Uri.Scheme)://$($Uri.Authority)"
    }}
}}
if (-not $Origin) {{
    $Origin = "{DEFAULT_NETLIFY_ORIGIN}"
}}

$Origin = $Origin.Trim().TrimEnd('/')
$ZipUrl = "$Origin/worker.zip"

# 2. Target directory in user profile (Zero Admin)
$TargetDir = Join-Path $env:USERPROFILE "DistributedMeshWorker"

# 3. Prompt for Coordinator endpoint if not provided
if (-not $Coordinator) {{
    Write-Host "Enter Coordinator URL (or press Enter for permanent cloud server):" -ForegroundColor Yellow
    $DefaultCoord = "https://ramusage-3656d30fbed9.herokuapp.com"
    $InputCoord = Read-Host "Coordinator URL [$DefaultCoord]"
    if ([string]::IsNullOrWhiteSpace($InputCoord)) {{
        $Coordinator = $DefaultCoord
    }} else {{
        $Coordinator = $InputCoord.Trim()
    }}
}}

if (-not $Coordinator.StartsWith("http")) {{
    $Coordinator = "http://$Coordinator"
}}

Write-Host "`n[*] Downloading worker bundle from: $ZipUrl" -ForegroundColor Gray
Write-Host "[*] Target installation folder:     $TargetDir" -ForegroundColor Gray
Write-Host "[*] Coordinator endpoint:           $Coordinator" -ForegroundColor Cyan

if (-not (Test-Path $TargetDir)) {{
    New-Item -ItemType Directory -Path $TargetDir -Force | Out-Null
}}

# 4. Download worker.zip
$ZipDest = Join-Path $env:TEMP "mesh_worker.zip"
Write-Host "[*] Downloading package..." -ForegroundColor Gray

try {{
    Invoke-WebRequest -Uri $ZipUrl -OutFile $ZipDest -UseBasicParsing
}} catch {{
    Write-Host "[!] Retrying with Invoke-RestMethod..." -ForegroundColor Yellow
    Invoke-RestMethod -Uri $ZipUrl -OutFile $ZipDest
}}

Write-Host "[*] Extracting package into $TargetDir..." -ForegroundColor Gray
Expand-Archive -Path $ZipDest -DestinationPath $TargetDir -Force
Remove-Item -Path $ZipDest -Force -ErrorAction SilentlyContinue

# 5. Update config.json with specified coordinator
$ConfigFile = Join-Path $TargetDir "config.json"
if (Test-Path $ConfigFile) {{
    try {{
        $Config = Get-Content $ConfigFile -Raw | ConvertFrom-Json
        $Config.worker.coordinator_url = $Coordinator
        $Config | ConvertTo-Json -Depth 10 | Set-Content $ConfigFile -Encoding UTF8
    }} catch {{
        Write-Warning "Could not update config.json directly, fallback to command line argument."
    }}
}}

# 6. Install dependencies in user mode
Write-Host "[*] Verifying Python and installing dependencies (User-Space, Zero Admin)..." -ForegroundColor Gray
$pythonCmd = (Get-Command python -ErrorAction SilentlyContinue).Source
if (-not $pythonCmd) {{
    Write-Host "[ERROR] Python 3 was not found in PATH! Please install Python 3.9+ and try again." -ForegroundColor Red
    return
}}

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
'''
    ps1_path = OUTPUT_DIR / "join.ps1"
    with open(ps1_path, "w", encoding="utf-8") as f:
        f.write(ps1_content)
    print(f"[+] Created {ps1_path.name}")


def write_join_bat():
    bat_content = rf'''@echo off
title DistributedMesh RAM Worker Setup
setlocal

echo ==============================================================
echo    DistributedMesh AI - RAM Worker One-Click Setup (CMD)
echo    Site: {DEFAULT_NETLIFY_ORIGIN}
echo ==============================================================
echo.

powershell -NoProfile -ExecutionPolicy Bypass -Command "$s='{DEFAULT_NETLIFY_ORIGIN}'; & ([scriptblock]::Create((irm \"$s/join.ps1\"))) -Origin $s"

pause
'''
    bat_path = OUTPUT_DIR / "join.bat"
    with open(bat_path, "w", encoding="utf-8") as f:
        f.write(bat_content)
    print(f"[+] Created {bat_path.name}")


def write_index_html():
    html_content = rf'''<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>DistributedMesh AI - RAM Cluster & Local Inference Control</title>
  <meta name="description" content="Connect LAN PCs to pool RAM for distributed local AI inference without admin rights or port forwarding. Controlled from PowerShell.">
  <link rel="preconnect" href="https://fonts.googleapis.com">
  <link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
  <link href="https://fonts.googleapis.com/css2?family=Outfit:wght@300;400;500;600;700&family=JetBrains+Mono:wght@400;500;600&display=swap" rel="stylesheet">
  <style>
    :root {{
      --bg: #07090e;
      --card-bg: rgba(15, 20, 31, 0.72);
      --card-border: rgba(255, 255, 255, 0.08);
      --border-glow: rgba(56, 189, 248, 0.35);
      --primary: #38bdf8;
      --primary-dark: #0284c7;
      --accent: #818cf8;
      --emerald: #10b981;
      --amber: #f59e0b;
      --text: #f1f5f9;
      --text-muted: #94a3b8;
      --code-bg: #0a0d14;
    }}

    * {{
      box-sizing: border-box;
      margin: 0;
      padding: 0;
    }}

    body {{
      background: radial-gradient(circle at 50% 0%, #151d33 0%, var(--bg) 65%);
      color: var(--text);
      font-family: 'Outfit', -apple-system, sans-serif;
      min-height: 100vh;
      display: flex;
      flex-direction: column;
      align-items: center;
      padding: 40px 20px 80px;
    }}

    .container {{
      max-width: 960px;
      width: 100%;
    }}

    /* Header */
    .header {{
      text-align: center;
      margin-bottom: 35px;
    }}

    .badge-bar {{
      display: inline-flex;
      align-items: center;
      gap: 10px;
      background: rgba(56, 189, 248, 0.1);
      border: 1px solid rgba(56, 189, 248, 0.25);
      padding: 6px 16px;
      border-radius: 999px;
      font-size: 0.82rem;
      font-weight: 600;
      letter-spacing: 0.5px;
      color: var(--primary);
      margin-bottom: 18px;
    }}

    .pulse-dot {{
      width: 8px;
      height: 8px;
      background: var(--emerald);
      border-radius: 50%;
      box-shadow: 0 0 10px var(--emerald);
      animation: pulse 2s infinite;
    }}

    @keyframes pulse {{
      0%, 100% {{ opacity: 1; transform: scale(1); }}
      50% {{ opacity: 0.4; transform: scale(0.85); }}
    }}

    h1 {{
      font-size: 2.8rem;
      font-weight: 700;
      letter-spacing: -0.5px;
      background: linear-gradient(135deg, #ffffff 40%, var(--primary) 100%);
      -webkit-background-clip: text;
      -webkit-text-fill-color: transparent;
      margin-bottom: 12px;
    }}

    .subtitle {{
      color: var(--text-muted);
      font-size: 1.1rem;
      max-width: 680px;
      margin: 0 auto;
      line-height: 1.6;
    }}

    /* Tabs Navigation */
    .tabs {{
      display: flex;
      gap: 8px;
      background: rgba(15, 23, 42, 0.6);
      border: 1px solid var(--card-border);
      padding: 6px;
      border-radius: 14px;
      margin-bottom: 28px;
      overflow-x: auto;
    }}

    .tab-btn {{
      background: transparent;
      border: none;
      color: var(--text-muted);
      font-family: 'Outfit', sans-serif;
      font-size: 0.92rem;
      font-weight: 500;
      padding: 10px 18px;
      border-radius: 10px;
      cursor: pointer;
      transition: all 0.2s ease;
      display: flex;
      align-items: center;
      gap: 8px;
      white-space: nowrap;
    }}

    .tab-btn:hover {{
      color: #fff;
      background: rgba(255, 255, 255, 0.05);
    }}

    .tab-btn.active {{
      background: linear-gradient(135deg, rgba(56, 189, 248, 0.18), rgba(129, 140, 248, 0.18));
      color: #fff;
      border: 1px solid rgba(56, 189, 248, 0.4);
      font-weight: 600;
      box-shadow: 0 4px 14px rgba(56, 189, 248, 0.15);
    }}

    /* Tab Content Panes */
    .tab-pane {{
      display: none;
      animation: fadeIn 0.25s ease;
    }}

    .tab-pane.active {{
      display: block;
    }}

    @keyframes fadeIn {{
      from {{ opacity: 0; transform: translateY(6px); }}
      to {{ opacity: 1; transform: translateY(0); }}
    }}

    /* Cards */
    .card {{
      background: var(--card-bg);
      backdrop-filter: blur(16px);
      border: 1px solid var(--card-border);
      border-radius: 18px;
      padding: 26px;
      margin-bottom: 22px;
      box-shadow: 0 16px 40px rgba(0, 0, 0, 0.45);
      transition: border-color 0.2s ease;
    }}

    .card:hover {{
      border-color: var(--border-glow);
    }}

    .card-header {{
      display: flex;
      align-items: center;
      justify-content: space-between;
      margin-bottom: 16px;
    }}

    .card-title {{
      font-size: 1.2rem;
      font-weight: 600;
      display: flex;
      align-items: center;
      gap: 12px;
      color: #fff;
    }}

    .step-pill {{
      background: linear-gradient(135deg, var(--primary), var(--accent));
      width: 28px;
      height: 28px;
      border-radius: 50%;
      display: flex;
      align-items: center;
      justify-content: center;
      font-size: 0.85rem;
      font-weight: 700;
      color: #000;
    }}

    .card-desc {{
      color: var(--text-muted);
      font-size: 0.92rem;
      margin-bottom: 14px;
      line-height: 1.5;
    }}

    /* Code Terminal Box */
    .terminal-box {{
      background: var(--code-bg);
      border: 1px solid rgba(255, 255, 255, 0.08);
      border-radius: 12px;
      padding: 12px 16px;
      display: flex;
      align-items: center;
      justify-content: space-between;
      gap: 12px;
      margin-bottom: 12px;
    }}

    .code-text {{
      font-family: 'JetBrains Mono', monospace;
      font-size: 0.88rem;
      color: #38bdf8;
      overflow-x: auto;
      white-space: nowrap;
      user-select: all;
    }}

    .copy-btn {{
      background: rgba(255, 255, 255, 0.08);
      border: 1px solid rgba(255, 255, 255, 0.12);
      color: #fff;
      font-family: 'Outfit', sans-serif;
      font-size: 0.82rem;
      font-weight: 500;
      padding: 7px 14px;
      border-radius: 8px;
      cursor: pointer;
      transition: all 0.2s ease;
      display: flex;
      align-items: center;
      gap: 6px;
      flex-shrink: 0;
    }}

    .copy-btn:hover {{
      background: var(--primary);
      border-color: var(--primary);
      color: #000;
      font-weight: 600;
      box-shadow: 0 0 16px rgba(56, 189, 248, 0.4);
    }}

    .copy-btn.copied {{
      background: var(--emerald);
      border-color: var(--emerald);
      color: #fff;
    }}

    /* Prompts Table */
    .prompt-card {{
      background: rgba(255, 255, 255, 0.025);
      border: 1px solid rgba(255, 255, 255, 0.06);
      border-radius: 12px;
      padding: 16px;
      margin-bottom: 12px;
      display: flex;
      flex-direction: column;
      gap: 10px;
    }}

    .prompt-header {{
      display: flex;
      align-items: center;
      justify-content: space-between;
    }}

    .prompt-tag {{
      font-size: 0.75rem;
      font-weight: 600;
      padding: 3px 8px;
      border-radius: 6px;
      text-transform: uppercase;
      letter-spacing: 0.5px;
    }}

    .tag-reasoning {{ background: rgba(129, 140, 248, 0.18); color: #a5b4fc; }}
    .tag-coding {{ background: rgba(56, 189, 248, 0.18); color: #7dd3fc; }}
    .tag-system {{ background: rgba(16, 185, 129, 0.18); color: #6ee7b7; }}

    /* Features Grid */
    .features-grid {{
      display: grid;
      grid-template-columns: repeat(auto-fit, minmax(260px, 1fr));
      gap: 16px;
      margin-top: 14px;
    }}

    .feature-item {{
      background: rgba(255, 255, 255, 0.025);
      border: 1px solid rgba(255, 255, 255, 0.06);
      border-radius: 12px;
      padding: 18px;
    }}

    .feature-item h4 {{
      font-size: 1rem;
      color: #fff;
      margin-bottom: 8px;
      display: flex;
      align-items: center;
      gap: 8px;
    }}

    .feature-item p {{
      font-size: 0.88rem;
      color: var(--text-muted);
      line-height: 1.5;
    }}

    /* Links table */
    .link-row {{
      display: flex;
      align-items: center;
      justify-content: space-between;
      padding: 14px 18px;
      background: rgba(255, 255, 255, 0.02);
      border: 1px solid rgba(255, 255, 255, 0.05);
      border-radius: 10px;
      margin-bottom: 10px;
      text-decoration: none;
      color: inherit;
      transition: all 0.2s ease;
    }}

    .link-row:hover {{
      background: rgba(255, 255, 255, 0.05);
      border-color: rgba(56, 189, 248, 0.3);
      transform: translateX(4px);
    }}

    .link-info h5 {{
      font-size: 0.95rem;
      color: #fff;
      margin-bottom: 3px;
    }}

    .link-info span {{
      font-size: 0.82rem;
      color: var(--text-muted);
    }}

    .link-action {{
      font-size: 0.85rem;
      color: var(--primary);
      font-weight: 600;
    }}

    /* Footer */
    footer {{
      margin-top: 50px;
      text-align: center;
      color: var(--text-muted);
      font-size: 0.85rem;
    }}
  </style>
</head>
<body>

  <div class="container">
    <!-- Header -->
    <header class="header">
      <div class="badge-bar">
        <span class="pulse-dot"></span>
        Zero Admin &bull; 100% Invisible Background &bull; ramusageailaptop.netlify.app
      </div>
      <h1>DistributedMesh AI</h1>
      <p class="subtitle">
        Pool the RAM of your Windows PCs across LAN for distributed local AI inference. Controlled seamlessly from PowerShell on your laptop.
      </p>
    </header>

    <!-- Navigation Tabs -->
    <nav class="tabs" role="tablist">
      <button class="tab-btn active" onclick="openTab('worker-tab', this)">🚀 1. Worker PC Setup</button>
      <button class="tab-btn" onclick="openTab('laptop-tab', this)">💻 2. Laptop Controller</button>
      <button class="tab-btn" onclick="openTab('prompts-tab', this)">🎯 3. Prompt Library</button>
      <button class="tab-btn" onclick="openTab('links-tab', this)">📁 4. Links & Downloads</button>
      <button class="tab-btn" onclick="openTab('faq-tab', this)">🧠 5. Architecture & FAQ</button>
    </nav>

    <!-- TAB 1: WORKER SETUP -->
    <div id="worker-tab" class="tab-pane active">
      <div class="card">
        <div class="card-header">
          <div class="card-title">
            <span class="step-pill">1</span>
            <span>Join Worker PC via PowerShell (Recommended)</span>
          </div>
        </div>
        <p class="card-desc">
          Run this on any Windows PC you want to use for RAM. Installs automatically in user-space, configures auto-start on boot, and runs 100% invisibly in the background.
        </p>
        <div class="terminal-box">
          <span class="code-text" id="cmdPs">$s='{DEFAULT_NETLIFY_ORIGIN}'; & ([scriptblock]::Create((irm "$s/join.ps1"))) -Origin $s</span>
          <button class="copy-btn" onclick="copySnippet('cmdPs', this)">
            <span>Copy</span>
          </button>
        </div>
      </div>

      <div class="card">
        <div class="card-header">
          <div class="card-title">
            <span class="step-pill">2</span>
            <span>Join Worker PC via Command Prompt (CMD)</span>
          </div>
        </div>
        <p class="card-desc">
          If you prefer standard Command Prompt (`cmd.exe`), run this one-liner:
        </p>
        <div class="terminal-box">
          <span class="code-text" id="cmdCmd">powershell -ep bypass -c "$s='{DEFAULT_NETLIFY_ORIGIN}'; & ([scriptblock]::Create((irm \"$s/join.ps1\"))) -Origin $s"</span>
          <button class="copy-btn" onclick="copySnippet('cmdCmd', this)">
            <span>Copy</span>
          </button>
        </div>
      </div>

      <div class="card">
        <div class="card-title">⚡ What Happens Automatically on the Worker PC</div>
        <div class="features-grid">
          <div class="feature-item">
            <h4>🛡️ Zero Admin Privileges</h4>
            <p>Runs entirely inside your Windows user profile (`%USERPROFILE%\DistributedMeshWorker`). Never asks for administrator elevation or UAC.</p>
          </div>
          <div class="feature-item">
            <h4>👻 100% Invisible Background</h4>
            <p>Runs silently using `pythonw.exe` and a headless VBScript runner. No taskbar icon, console window, or popups appear.</p>
          </div>
          <div class="feature-item">
            <h4>🔄 Power Outage Auto-Start</h4>
            <p>Configured in Windows startup (`HKCU\Run`). Whenever electricity turns back on, the node automatically launches and connects.</p>
          </div>
          <div class="feature-item">
            <h4>🧠 Zero Model Upload</h4>
            <p>Scans existing models in LM Studio and Ollama directly from the local hard drive. No multi-gigabyte uploads needed.</p>
          </div>
        </div>
      </div>
    </div>

    <!-- TAB 2: LAPTOP CONTROLLER -->
    <div id="laptop-tab" class="tab-pane">
      <div class="card">
        <div class="card-title">💻 PowerShell Laptop Control Commands</div>
        <p class="card-desc">
          From your laptop, open PowerShell in the project folder and use `.\mesh.ps1` to control everything:
        </p>

        <!-- Command 1: PCS -->
        <div class="terminal-box">
          <span class="code-text" id="lpPcs">.\mesh.ps1 pcs</span>
          <button class="copy-btn" onclick="copySnippet('lpPcs', this)"><span>Copy</span></button>
        </div>
        <p style="font-size: 0.84rem; color: var(--text-muted); margin: -4px 0 14px 4px;">
          Shows total connected PCs (online vs offline), IP addresses, and free RAM per machine.
        </p>

        <!-- Command 2: MODELS -->
        <div class="terminal-box">
          <span class="code-text" id="lpModels">.\mesh.ps1 models</span>
          <button class="copy-btn" onclick="copySnippet('lpModels', this)"><span>Copy</span></button>
        </div>
        <p style="font-size: 0.84rem; color: var(--text-muted); margin: -4px 0 14px 4px;">
          Lists all downloaded models found across all PCs (LM Studio, Ollama, GGUF) with parameters and layer counts.
        </p>

        <!-- Command 3: LOAD -->
        <div class="terminal-box">
          <span class="code-text" id="lpLoad">.\mesh.ps1 load 1</span>
          <button class="copy-btn" onclick="copySnippet('lpLoad', this)"><span>Copy</span></button>
        </div>
        <p style="font-size: 0.84rem; color: var(--text-muted); margin: -4px 0 14px 4px;">
          Loads model #1. The cluster calculates each PC's free RAM, splits the layers, and activates distributed inference.
        </p>

        <!-- Command 4: ASK -->
        <div class="terminal-box">
          <span class="code-text" id="lpAsk">.\mesh.ps1 ask "Hello! What can you help me with?"</span>
          <button class="copy-btn" onclick="copySnippet('lpAsk', this)"><span>Copy</span></button>
        </div>
        <p style="font-size: 0.84rem; color: var(--text-muted); margin: -4px 0 14px 4px;">
          Sends an inference prompt directly to the distributed AI cluster.
        </p>

        <!-- Command 5: CLEAN -->
        <div class="terminal-box">
          <span class="code-text" id="lpClean">.\mesh.ps1 clean</span>
          <button class="copy-btn" onclick="copySnippet('lpClean', this)"><span>Copy</span></button>
        </div>
        <p style="font-size: 0.84rem; color: var(--text-muted); margin: -4px 0 14px 4px;">
          Flushes process working sets and reclaims unused RAM across all connected computers.
        </p>

        <!-- Command 6: UNLOAD -->
        <!-- Command 6: UNLOAD -->
        <div class="terminal-box">
          <span class="code-text" id="lpUnload">.\mesh.ps1 unload</span>
          <button class="copy-btn" onclick="copySnippet('lpUnload', this)"><span>Copy</span></button>
        </div>
        <p style="font-size: 0.84rem; color: var(--text-muted); margin: -4px 0 14px 4px;">
          Unloads active model and releases all memory allocations.
        </p>

        <!-- Command 7: CODE RED (Wipe & Clean Uninstall) -->
        <div style="margin-top: 24px; padding: 18px; background: rgba(239, 68, 68, 0.08); border: 1px solid rgba(239, 68, 68, 0.3); border-radius: 14px;">
          <h4 style="color: #f87171; display: flex; align-items: center; gap: 8px; margin-bottom: 8px; font-size: 1.05rem;">
            🚨 CODE RED: Remote Wipe & Clean Uninstall
          </h4>
          <p style="font-size: 0.86rem; color: #fca5a5; line-height: 1.5; margin-bottom: 12px;">
            Sends a self-destruct wipe signal to all worker PCs. Kills all running worker processes, removes Windows startup registry keys, and deletes the entire application folder and logs as if the software never existed.
          </p>
          <div class="terminal-box" style="margin-bottom: 0; border-color: rgba(239, 68, 68, 0.4); background: #130a0d;">
            <span class="code-text" id="lpCodeRed" style="color: #fca5a5;">.\mesh.ps1 codered</span>
            <button class="copy-btn" onclick="copySnippet('lpCodeRed', this)" style="background: rgba(239, 68, 68, 0.25); border-color: rgba(239, 68, 68, 0.5); color: #fff;"><span>Copy</span></button>
          </div>
        </div>
      </div>
    </div>

    <!-- TAB 3: PROMPTS LIBRARY -->
    <div id="prompts-tab" class="tab-pane">
      <div class="card">
        <div class="card-title">🎯 Ready-to-Run Inference Prompts</div>
        <p class="card-desc">
          Test your distributed AI cluster with these prompts. Click "Copy" to paste directly into your PowerShell terminal:
        </p>

        <!-- Prompt 1 -->
        <div class="prompt-card">
          <div class="prompt-header">
            <span class="prompt-tag tag-coding">Coding & Performance</span>
            <span style="font-size: 0.82rem; color: var(--text-muted);">Python RAM Benchmark</span>
          </div>
          <div class="terminal-box" style="margin-bottom: 0;">
            <span class="code-text" id="pCode">.\mesh.ps1 ask "Write a fast Python script to benchmark memory throughput across multiple CPU cores"</span>
            <button class="copy-btn" onclick="copySnippet('pCode', this)"><span>Copy</span></button>
          </div>
        </div>

        <!-- Prompt 2 -->
        <div class="prompt-card">
          <div class="prompt-header">
            <span class="prompt-tag tag-reasoning">Complex Reasoning</span>
            <span style="font-size: 0.82rem; color: var(--text-muted);">Physics / Science</span>
          </div>
          <div class="terminal-box" style="margin-bottom: 0;">
            <span class="code-text" id="pReason">.\mesh.ps1 ask "Explain quantum entanglement and quantum computing in simple terms for a 12 year old"</span>
            <button class="copy-btn" onclick="copySnippet('pReason', this)"><span>Copy</span></button>
          </div>
        </div>

        <!-- Prompt 3 -->
        <div class="prompt-card">
          <div class="prompt-header">
            <span class="prompt-tag tag-system">Architecture Analysis</span>
            <span style="font-size: 0.82rem; color: var(--text-muted);">Distributed AI Systems</span>
          </div>
          <div class="terminal-box" style="margin-bottom: 0;">
            <span class="code-text" id="pArch">.\mesh.ps1 ask "Summarize the architectural advantages of distributed layer splitting over LAN vs single-GPU inference"</span>
            <button class="copy-btn" onclick="copySnippet('pArch', this)"><span>Copy</span></button>
          </div>
        </div>

        <!-- Prompt 4 -->
        <div class="prompt-card">
          <div class="prompt-header">
            <span class="prompt-tag tag-reasoning">Creative Writing</span>
            <span style="font-size: 0.82rem; color: var(--text-muted);">Sci-Fi Story</span>
          </div>
          <div class="terminal-box" style="margin-bottom: 0;">
            <span class="code-text" id="pStory">.\mesh.ps1 ask "Write a gripping sci-fi short story about an AI mind distributed across salvaged office computers"</span>
            <button class="copy-btn" onclick="copySnippet('pStory', this)"><span>Copy</span></button>
          </div>
        </div>
      </div>
    </div>

    <!-- TAB 4: LINKS & DOWNLOADS -->
    <div id="links-tab" class="tab-pane">
      <div class="card">
        <div class="card-title">📁 Important Links & Raw Downloads</div>
        <p class="card-desc">Direct links to download scripts and raw components hosted on this site:</p>

        <a class="link-row" href="worker.zip" download>
          <div class="link-info">
            <h5>📦 worker.zip (Lightweight Bundle)</h5>
            <span>Complete worker engine, background watchdog, and RAM monitor (~19 KB)</span>
          </div>
          <div class="link-action">Download ZIP &darr;</div>
        </a>

        <a class="link-row" href="join.ps1" target="_blank">
          <div class="link-info">
            <h5>📜 join.ps1 (PowerShell Installer)</h5>
            <span>Raw PowerShell 1-click installer script executed by worker nodes</span>
          </div>
          <div class="link-action">View Script &rarr;</div>
        </a>

        <a class="link-row" href="join.bat" target="_blank">
          <div class="link-info">
            <h5>📜 join.bat (CMD Batch Launcher)</h5>
            <span>Standard Windows batch file wrapper for cmd.exe</span>
          </div>
          <div class="link-action">View Script &rarr;</div>
        </a>

        <a class="link-row" href="uninstall_worker.bat" download>
          <div class="link-info">
            <h5>🚨 uninstall_worker.bat (Local Uninstaller)</h5>
            <span>Standalone batch file to cleanly wipe the software locally from any worker PC</span>
          </div>
          <div class="link-action">Download BAT &darr;</div>
        </a>

        <a class="link-row" href="{DEFAULT_NETLIFY_ORIGIN}" target="_blank">
          <div class="link-info">
            <h5>🌐 Official Web Portal</h5>
            <span>{DEFAULT_NETLIFY_ORIGIN}</span>
          </div>
          <div class="link-action">Open Link &rarr;</div>
        </a>
      </div>
    </div>

    <!-- TAB 5: ARCHITECTURE & FAQ -->
    <div id="faq-tab" class="tab-pane">
      <div class="card">
        <div class="card-title">🧠 Architecture & Frequently Asked Questions</div>
        
        <div style="margin-top: 16px; display: flex; flex-direction: column; gap: 16px;">
          <div>
            <h4 style="color: #fff; margin-bottom: 6px;">Q: Do I need to download the model on every computer?</h4>
            <p style="color: var(--text-muted); font-size: 0.9rem; line-height: 1.5;">
              <strong>NO.</strong> You only download the model file on <strong>one computer</strong> (e.g. in LM Studio). When you choose that model, the system reads the model weights from that disk and streams the assigned layers directly into the other computers' RAM over LAN. The other computers use zero hard drive space!
            </p>
          </div>

          <div>
            <h4 style="color: #fff; margin-bottom: 6px;">Q: What happens if electricity goes off and comes back on?</h4>
            <p style="color: var(--text-muted); font-size: 0.9rem; line-height: 1.5;">
              As long as your PC BIOS is set to "Restore on AC Power Loss: Power On", Windows turns on automatically. The worker node is registered in your Windows startup folder and silently reconnects to the Master PC as soon as the network comes online.
            </p>
          </div>

          <div>
            <h4 style="color: #fff; margin-bottom: 6px;">Q: Do I need a Telegram bot token right now?</h4>
            <p style="color: var(--text-muted); font-size: 0.9rem; line-height: 1.5;">
              <strong>NO.</strong> You have full control from your laptop using PowerShell (`.\mesh.ps1`). Telegram is 100% optional and disabled by default.
            </p>
          </div>

          <div>
            <h4 style="color: #fff; margin-bottom: 6px;">Q: Does any script require Administrator rights?</h4>
            <p style="color: var(--text-muted); font-size: 0.9rem; line-height: 1.5;">
              <strong>None.</strong> Everything installs and runs in user-space permissions (`pip install --user`, HKCU registry keys, Win32 memory APIs).
            </p>
          </div>
        </div>
      </div>
    </div>

    <!-- Footer -->
    <footer>
      DistributedMesh AI &bull; Hosted on Netlify &bull; Designed for Zero-Admin Windows LAN Clusters
    </footer>
  </div>

  <script>
    function openTab(tabId, btn) {{
      document.querySelectorAll('.tab-pane').forEach(el => el.classList.remove('active'));
      document.querySelectorAll('.tab-btn').forEach(el => el.classList.remove('active'));
      document.getElementById(tabId).classList.add('active');
      btn.classList.add('active');
    }}

    function copySnippet(elementId, btn) {{
      const text = document.getElementById(elementId).innerText;
      navigator.clipboard.writeText(text).then(() => {{
        const originalHtml = btn.innerHTML;
        btn.innerHTML = '<span>✓ Copied!</span>';
        btn.classList.add('copied');
        setTimeout(() => {{
          btn.innerHTML = originalHtml;
          btn.classList.remove('copied');
        }}, 2000);
      }}).catch(() => {{
        const ta = document.createElement('textarea');
        ta.value = text;
        document.body.appendChild(ta);
        ta.select();
        document.execCommand('copy');
        document.body.removeChild(ta);
        btn.innerHTML = '<span>✓ Copied!</span>';
        btn.classList.add('copied');
        setTimeout(() => {{
          btn.innerHTML = '<span>Copy</span>';
          btn.classList.remove('copied');
        }}, 2000);
      }});
    }}
  </script>
</body>
</html>
'''
    html_path = OUTPUT_DIR / "index.html"
    with open(html_path, "w", encoding="utf-8") as f:
        f.write(html_content)
    print(f"[+] Created {html_path.name}")


def main():
    print("==============================================================")
    print(f" Packaging DistributedMesh AI for {DEFAULT_NETLIFY_ORIGIN}")
    print("==============================================================")
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    build_worker_zip()
    write_join_ps1()
    write_join_bat()
    write_index_html()

    uninstall_src = BASE_DIR / "uninstall_worker.bat"
    if uninstall_src.exists():
        shutil.copy2(uninstall_src, OUTPUT_DIR / "uninstall_worker.bat")
        print(f"[+] Copied uninstall_worker.bat to {OUTPUT_DIR.name}/")

    print("==============================================================")
    print(f"[SUCCESS] 'netlify_deploy/' ready for: {DEFAULT_NETLIFY_ORIGIN}")
    print(f"Directory: {OUTPUT_DIR}")
    print("==============================================================")


if __name__ == "__main__":
    main()
