<#
.SYNOPSIS
  DistributedMesh AI - Native PowerShell Cluster Controller
  Control your LAN AI cluster directly from PowerShell on your laptop.
  Zero admin rights required.

.EXAMPLE
  .\mesh.ps1 models
  .\mesh.ps1 load 1
  .\mesh.ps1 ask "What is distributed inference?"
  .\mesh.ps1 pcs
  .\mesh.ps1 clean
  .\mesh.ps1 unload
  .\mesh.ps1 codered
  .\mesh.ps1 (Interactive Mode)
#>

[CmdletBinding()]
param (
    [Parameter(Position = 0)]
    [string]$Action = "",

    [Parameter(Position = 1, ValueFromRemainingArguments = $true)]
    [string[]]$Arguments,

    [Parameter()]
    [string]$Url = ""
)

# Load URL from config.json if not provided
if (-not $Url) {
    $configFile = Join-Path $PSScriptRoot "config.json"
    if (Test-Path $configFile) {
        try {
            $cfg = Get-Content $configFile -Raw | ConvertFrom-Json
            $cHost = $cfg.coordinator.host
            $cPort = $cfg.coordinator.port
            if ($cHost -eq "0.0.0.0") { $cHost = "127.0.0.1" }
            $Url = "http://${cHost}:${cPort}"
        } catch {
            $Url = "http://127.0.0.1:8500"
        }
    } else {
        $Url = "http://127.0.0.1:8500"
    }
}
$Url = $Url.TrimEnd('/')

function Format-Bytes([double]$mb) {
    if ($mb -ge 1024) {
        return "$([math]::Round($mb / 1024, 2)) GB"
    }
    return "$([math]::Round($mb, 1)) MB"
}

function Show-Models {
    Write-Host ""
    Write-Host "======================================================================" -ForegroundColor Cyan
    Write-Host "  [MODELS] Local AI Models (LM Studio, Ollama, and Local Files)" -ForegroundColor Cyan
    Write-Host "======================================================================" -ForegroundColor Cyan
    try {
        $models = Invoke-RestMethod -Uri "$Url/api/models" -Method Get -TimeoutSec 10
        if (-not $models -or $models.Count -eq 0) {
            Write-Host "  No models detected in LM Studio or models/ folder." -ForegroundColor Yellow
            Write-Host "  Models downloaded in LM Studio will automatically show up here." -ForegroundColor DarkGray
        } else {
            $idx = 1
            foreach ($m in $models) {
                Write-Host "  [$idx] $($m.name)" -ForegroundColor Green
                Write-Host "      Size: $($m.size_gb) GB | Arch: $($m.architecture) | Layers: $($m.layers) | Quant: $($m.quantization)" -ForegroundColor White
                Write-Host "      Source: $($m.source) | Node: $(if ($m.node_id) { $m.node_id } else { 'LAN' })" -ForegroundColor DarkGray
                $idx++
            }
            Write-Host ""
            Write-Host "  To run a model across cluster:  .\mesh.ps1 load 1" -ForegroundColor Yellow
        }
    } catch {
        Write-Host "  [ERROR] Could not connect to Coordinator at $Url" -ForegroundColor Red
        Write-Host "  Details: $($_.Exception.Message)" -ForegroundColor DarkRed
    }
    Write-Host "======================================================================" -ForegroundColor Cyan
    Write-Host ""
}

function Load-Model([string]$Identifier) {
    if (-not $Identifier) {
        Write-Host "Please specify a model number or name: .\mesh.ps1 load 1" -ForegroundColor Yellow
        return
    }

    try {
        $models = Invoke-RestMethod -Uri "$Url/api/models" -Method Get -TimeoutSec 10
        $target = $null

        if ($Identifier -match '^\d+$') {
            $idx = [int]$Identifier - 1
            if ($idx -ge 0 -and $idx -lt $models.Count) {
                $target = $models[$idx]
            }
        } else {
            $target = $models | Where-Object { $_.name -like "*$Identifier*" } | Select-Object -First 1
        }

        if ($target) {
            $req = @{
                model_name = $target.name
                layers = [int]$target.layers
                size_mb = [double]$target.size_mb
            }
        } else {
            $req = @{
                model_name = $Identifier
                layers = 32
                size_mb = 4800.0
            }
        }

        Write-Host ""
        Write-Host "[INFO] Inspecting free RAM and deploying '$($req.model_name)' across PCs..." -ForegroundColor Cyan

        $body = $req | ConvertTo-Json
        $resp = Invoke-RestMethod -Uri "$Url/api/models/load" -Method Post -Body $body -ContentType "application/json" -TimeoutSec 20

        if ($resp.success) {
            Write-Host ""
            Write-Host "======================================================================" -ForegroundColor Green
            Write-Host "  [SUCCESS] Model '$($req.model_name)' Loaded and Running on Cluster!" -ForegroundColor Green
            Write-Host "======================================================================" -ForegroundColor Green
            foreach ($alloc in $resp.plan.allocations) {
                $ramStr = Format-Bytes $alloc.assigned_ram_mb
                Write-Host "  - $($alloc.node_id): $($alloc.layers) layers (L$($alloc.start_layer)-L$($alloc.end_layer)) | RAM: ~$ramStr" -ForegroundColor White
            }
            if ($resp.plan.rpc_endpoints) {
                Write-Host ""
                Write-Host "  RPC Endpoints: $($resp.plan.rpc_endpoints -join ', ')" -ForegroundColor DarkGray
            }
            Write-Host "======================================================================" -ForegroundColor Green
            Write-Host "  Now send prompts using: .\mesh.ps1 ask `"your question`"" -ForegroundColor Yellow
            Write-Host ""
        }
    } catch {
        Write-Host "[ERROR] Failed to load model: $($_.Exception.Message)" -ForegroundColor Red
    }
}

function Unload-Model {
    try {
        Write-Host "[INFO] Unloading active model and freeing cluster RAM..." -ForegroundColor Cyan
        $resp = Invoke-RestMethod -Uri "$Url/api/models/unload" -Method Post -TimeoutSec 10
        Write-Host "[SUCCESS] $($resp.message)" -ForegroundColor Green
    } catch {
        Write-Host "[ERROR] $($_.Exception.Message)" -ForegroundColor Red
    }
}

function Show-Pcs {
    Write-Host ""
    Write-Host "======================================================================" -ForegroundColor Cyan
    Write-Host "  [PCS] Connected PCs on LAN Cluster" -ForegroundColor Cyan
    Write-Host "======================================================================" -ForegroundColor Cyan
    try {
        $data = Invoke-RestMethod -Uri "$Url/api/pcs" -Method Get -TimeoutSec 8
        Write-Host "  Total Registered PCs: $($data.total_pcs)" -ForegroundColor White
        Write-Host "  - Online PCs:         $($data.online_pcs)" -ForegroundColor Green
        Write-Host "  - Offline PCs:        $($data.offline_pcs)" -ForegroundColor Red
        Write-Host "----------------------------------------------------------------------" -ForegroundColor DarkGray

        $i = 1
        foreach ($pc in $data.pcs) {
            $stateSym = if ($pc.status -eq "online") { "[ONLINE]" } else { "[OFFLINE]" }
            $freeRam = Format-Bytes $pc.avail_ram_mb
            $totRam = Format-Bytes $pc.total_ram_mb
            $rpcState = if ($pc.rpc_running) { "RPC: ON" } else { "RPC: OFF" }
            Write-Host "  $i. $($pc.node_id.PadRight(15)) $stateSym  IP: $($pc.ip_address.PadRight(15)) RAM: $freeRam / $totRam | CPU: $($pc.cpu_percent)% | $rpcState" -ForegroundColor White
            $i++
        }
    } catch {
        Write-Host "  [ERROR] Cannot connect to Coordinator at $Url" -ForegroundColor Red
    }
    Write-Host "======================================================================" -ForegroundColor Cyan
    Write-Host ""
}

function Show-Status {
    try {
        $data = Invoke-RestMethod -Uri "$Url/api/status" -Method Get -TimeoutSec 8
        $tot = $data.total_cluster_ram_gb
        $free = $data.free_cluster_ram_gb
        $used = [math]::Max(0.0, $tot - $free)
        $pct = if ($tot -gt 0) { [math]::Round(($used / $tot) * 100) } else { 0 }

        Write-Host ""
        Write-Host "======================================================================" -ForegroundColor Cyan
        Write-Host "  Cluster: $($data.cluster_name)" -ForegroundColor Cyan
        Write-Host "  - Connected PCs: $($data.online_nodes) Online ($($data.total_nodes) Total)" -ForegroundColor White
        Write-Host "  - RAM Usage:     $([math]::Round($used, 1)) GB / $([math]::Round($tot, 1)) GB ($pct% used)" -ForegroundColor White
        Write-Host "  - Free RAM:      $([math]::Round($free, 2)) GB Available across cluster" -ForegroundColor Green
        Write-Host "  - Active Model:  $(if ($data.active_model) { $data.active_model } else { 'None (Idle)' })" -ForegroundColor Yellow
        Write-Host "======================================================================" -ForegroundColor Cyan
        Write-Host ""
    } catch {
        Write-Host "[ERROR] Cannot reach Coordinator at ${Url} - $($_.Exception.Message)" -ForegroundColor Red
    }
}

function Send-Prompt([string]$PromptText) {
    if (-not $PromptText) {
        Write-Host "Usage: .\mesh.ps1 ask `"your prompt here`"" -ForegroundColor Yellow
        return
    }
    try {
        Write-Host ""
        Write-Host "[INFO] Dispatching prompt to cluster..." -ForegroundColor Cyan
        $body = @{ prompt = $PromptText; max_tokens = 256 } | ConvertTo-Json
        $resp = Invoke-RestMethod -Uri "$Url/api/infer" -Method Post -Body $body -ContentType "application/json" -TimeoutSec 60

        if ($resp.success) {
            Write-Host ""
            Write-Host "[CLUSTER OUTPUT]:" -ForegroundColor Green
            Write-Host $resp.text -ForegroundColor White
            Write-Host ""
            Write-Host "Generated $($resp.tokens_generated) tokens in $($resp.elapsed_sec)s" -ForegroundColor DarkGray
            Write-Host ""
        } else {
            Write-Host "[ERROR] $($resp.error)" -ForegroundColor Red
        }
    } catch {
        Write-Host "[ERROR] Inference failed: $($_.Exception.Message)" -ForegroundColor Red
    }
}

function Clean-Ram {
    try {
        Write-Host "[INFO] Purging and trimming working set RAM across all PCs..." -ForegroundColor Cyan
        $resp = Invoke-RestMethod -Uri "$Url/api/trim" -Method Post -TimeoutSec 15
        Write-Host "[SUCCESS] RAM trim complete across all cluster nodes." -ForegroundColor Green
    } catch {
        Write-Host "[ERROR] $($_.Exception.Message)" -ForegroundColor Red
    }
}

function Invoke-CodeRed {
    Write-Host ""
    Write-Host "======================================================================" -ForegroundColor Red
    Write-Host "  [CODE RED] CLUSTER PURGE AND UNINSTALL PROTOCOL" -ForegroundColor Red
    Write-Host "======================================================================" -ForegroundColor Red
    Write-Host "  This command will:" -ForegroundColor Yellow
    Write-Host "    1. Send uninstall and self-destruct signal to all connected Worker PCs." -ForegroundColor White
    Write-Host "    2. Terminate all background worker processes and watchdogs." -ForegroundColor White
    Write-Host "    3. Remove all auto-start registry keys and startup shortcuts." -ForegroundColor White
    Write-Host "    4. Completely delete the application directory and logs." -ForegroundColor White
    Write-Host "    5. Leave the worker computers completely clean." -ForegroundColor White
    Write-Host ""
    Write-Host "  [!] WARNING: This action cannot be undone." -ForegroundColor Red
    Write-Host ""

    $confirm = Read-Host "Type 'CONFIRM' to execute CODE RED across all worker PCs"
    if ($confirm -ne "CONFIRM") {
        Write-Host ""
        Write-Host "  [CANCELLED] Code Red aborted. No changes were made." -ForegroundColor Green
        Write-Host "======================================================================" -ForegroundColor Red
        Write-Host ""
        return
    }

    Write-Host ""
    Write-Host "  [!] Broadcasting CODE RED uninstall signal to all Worker PCs..." -ForegroundColor Red
    try {
        $resp = Invoke-RestMethod -Uri "$Url/api/cluster/codered" -Method Post -TimeoutSec 15
        Write-Host "  [+] Coordinator response:" -ForegroundColor White
        Write-Host "      $($resp.message)" -ForegroundColor Green
        if ($resp.results) {
            foreach ($prop in $resp.results.PSObject.Properties) {
                Write-Host "      - PC $($prop.Name): $($prop.Value.message)" -ForegroundColor Yellow
            }
        }
        Write-Host ""
        Write-Host "  [SUCCESS] All worker PCs have been wiped and uninstalled cleanly." -ForegroundColor Green
    } catch {
        Write-Host "  [ERROR] Failed to send Code Red command: $($_.Exception.Message)" -ForegroundColor Red
    }
    Write-Host "======================================================================" -ForegroundColor Red
    Write-Host ""
}

# --- Action Dispatcher ---
$argString = ($Arguments -join " ").Trim()

switch ($Action.ToLower()) {
    "models"    { Show-Models }
    "list"      { Show-Models }
    "load"      { Load-Model $argString }
    "run"       { Load-Model $argString }
    "unload"    { Unload-Model }
    "stop"      { Unload-Model }
    "pcs"       { Show-Pcs }
    "count"     { Show-Pcs }
    "status"    { Show-Status }
    "ask"       { Send-Prompt $argString }
    "infer"     { Send-Prompt $argString }
    "clean"     { Clean-Ram }
    "trim"      { Clean-Ram }
    "codered"   { Invoke-CodeRed }
    "purge"     { Invoke-CodeRed }
    "uninstall" { Invoke-CodeRed }
    "nuke"      { Invoke-CodeRed }
    "help"      {
        Write-Host "DistributedMesh AI - PowerShell Commands:" -ForegroundColor Cyan
        Write-Host "  .\mesh.ps1 models        - List all local AI models (LM Studio and files)"
        Write-Host "  .\mesh.ps1 load <id>     - Automatically split and run model on PCs"
        Write-Host "  .\mesh.ps1 unload        - Unload active model and free cluster RAM"
        Write-Host "  .\mesh.ps1 ask `"<text>`"  - Send prompt to model and stream response"
        Write-Host "  .\mesh.ps1 pcs           - Show exact count and status of all PCs"
        Write-Host "  .\mesh.ps1 status        - Show cluster RAM load and active status"
        Write-Host "  .\mesh.ps1 clean         - Purge and trim working set memory on all PCs"
        Write-Host "  .\mesh.ps1 codered       - Purge and completely uninstall from all worker PCs" -ForegroundColor Red
        Write-Host "  .\mesh.ps1               - Launch interactive PowerShell shell"
    }
    default {
        if ($Action) {
            Write-Host "Unknown action '$Action'. Type .\mesh.ps1 help for commands." -ForegroundColor Yellow
        } else {
            # Interactive Mode
            Write-Host ""
            Write-Host "======================================================================" -ForegroundColor Cyan
            Write-Host "  DistributedMesh AI - Interactive PowerShell Controller" -ForegroundColor Cyan
            Write-Host "  Target Coordinator: $Url" -ForegroundColor DarkGray
            Write-Host "  Type 'help' for commands, 'exit' to quit." -ForegroundColor DarkGray
            Write-Host "======================================================================" -ForegroundColor Cyan
            Write-Host ""

            while ($true) {
                $line = Read-Host "mesh-ps"
                if (-not $line) { continue }
                $p = $line.Trim().Split(' ', 2)
                $cmd = $p[0].ToLower()
                $arg = if ($p.Length -gt 1) { $p[1].Trim() } else { "" }

                switch ($cmd) {
                    "exit"      { return }
                    "quit"      { return }
                    "q"         { return }
                    "models"    { Show-Models }
                    "list"      { Show-Models }
                    "m"         { Show-Models }
                    "load"      { Load-Model $arg }
                    "run"       { Load-Model $arg }
                    "unload"    { Unload-Model }
                    "pcs"       { Show-Pcs }
                    "count"     { Show-Pcs }
                    "status"    { Show-Status }
                    "s"         { Show-Status }
                    "ask"       { Send-Prompt $arg }
                    "clean"     { Clean-Ram }
                    "trim"      { Clean-Ram }
                    "codered"   { Invoke-CodeRed }
                    "purge"     { Invoke-CodeRed }
                    "uninstall" { Invoke-CodeRed }
                    "help"      {
                        Write-Host "Commands: models, load <num>, unload, pcs, status, ask `"<text>`", clean, codered, exit" -ForegroundColor Yellow
                    }
                    default {
                        Write-Host "Unknown command '$cmd'. Type 'help' for options." -ForegroundColor Yellow
                    }
                }
            }
        }
    }
}
