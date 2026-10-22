"""Worker node agent running on each LAN PC.
Monitors local RAM, executes OOM protection, runs RPC inference backend,
and reports status to the central Coordinator.
"""

import argparse
import asyncio
import os
import platform
import sys
import threading
import time
from typing import Any, Dict


def prevent_windows_sleep():
    """Keep Windows system and CPU active so background worker runs 24/7 even when locked.
    Allows the display/monitor to turn off to save power."""
    try:
        if sys.platform == "win32":
            import ctypes
            ES_CONTINUOUS = 0x80000000
            ES_SYSTEM_REQUIRED = 0x00000001
            ES_AWAYMODE_REQUIRED = 0x00000040
            ctypes.windll.kernel32.SetThreadExecutionState(ES_CONTINUOUS | ES_SYSTEM_REQUIRED | ES_AWAYMODE_REQUIRED)
    except Exception:
        pass

import psutil
import requests
import uvicorn
from fastapi import FastAPI, HTTPException, Request, Depends
from pydantic import BaseModel

from common.model_scanner import LocalModelInfo, scan_local_models
from common.models import NodeInfo, NodeMemoryStats
from common.utils import get_hostname, get_lan_ip, load_config
from worker.ram_monitor import OOMGuard, collect_node_memory, trim_all_worker_memory, trim_process_memory
from worker.rpc_manager import RPCManager


app = FastAPI(title="DistributedMesh Worker Node", version="1.0.0")

# Global node state container
class WorkerState:
    node_id: str = get_hostname()
    hostname: str = get_hostname()
    ip_address: str = get_lan_ip()
    port: int = 8501
    rpc_port: int = 50052
    coordinator_url: str = "http://127.0.0.1:8500"
    heartbeat_interval_sec: float = 3.0
    shared_secret: str = os.environ.get("CLUSTER_SECRET", "menabdul333")
    status: str = "online"
    rpc_manager: RPCManager = None  # type: ignore
    oom_guard: OOMGuard = None      # type: ignore
    allocated_layers: int = 0
    rpc_desired: bool = False
    running: bool = True
    custom_model_dirs: list[str] = []


state = WorkerState()


def is_worker_authenticated(request: Request) -> bool:
    if not state.shared_secret:
        return True
    hdr = request.headers.get("X-Cluster-Secret")
    if hdr and hdr.strip() == state.shared_secret:
        return True
    param = request.query_params.get("secret")
    if param and param.strip() == state.shared_secret:
        return True
    return False


def require_worker_auth(request: Request):
    if not is_worker_authenticated(request):
        raise HTTPException(status_code=401, detail="Unauthorized: Worker secret mismatch.")


class StartRPCRequest(BaseModel):
    memory_limit_mb: float = 0.0


@app.get("/")
def root():
    return {"status": "ok", "node_id": state.node_id, "role": "worker"}


@app.get("/models", response_model=list[LocalModelInfo], dependencies=[Depends(require_worker_auth)])
def get_models():
    """Scan and return all local AI models (LM Studio, GGUFs, project models) on this PC."""
    return scan_local_models(custom_paths=state.custom_model_dirs, node_id=state.node_id)


@app.get("/status", response_model=NodeInfo)
def get_status():
    mem = collect_node_memory(
        worker_pid=state.rpc_manager.pid if state.rpc_manager else None,
        critical_threshold_mb=state.oom_guard.critical_ram_mb if state.oom_guard else 400.0,
    )
    status_str = "critical_ram" if mem.is_oom_critical else state.status
    return NodeInfo(
        node_id=state.node_id,
        hostname=state.hostname,
        ip_address=state.ip_address,
        port=state.port,
        rpc_port=state.rpc_port,
        status=status_str,
        last_heartbeat=time.time(),
        memory=mem,
        allocated_layers=state.allocated_layers,
        cpu_percent=psutil.cpu_percent(interval=None),
        os_info=f"Windows {platform.release()}",
        worker_pid=state.rpc_manager.pid if state.rpc_manager else None,
        rpc_running=state.rpc_manager.is_running if state.rpc_manager else False,
    )


@app.post("/trim", dependencies=[Depends(require_worker_auth)])
def trim_memory():
    """Trigger immediate working set trim and garbage collection."""
    before_mem = collect_node_memory()
    pids = []
    if state.rpc_manager and state.rpc_manager.pid:
        pids.append(state.rpc_manager.pid)
    success_count = trim_all_worker_memory(pids)
    time.sleep(0.1)
    after_mem = collect_node_memory()
    freed_mb = max(0.0, after_mem.avail_ram_mb - before_mem.avail_ram_mb)
    return {
        "success": True,
        "trimmed_processes": success_count,
        "freed_ram_mb": round(freed_mb, 1),
        "available_ram_mb": after_mem.avail_ram_mb,
    }


@app.post("/rpc/start", dependencies=[Depends(require_worker_auth)])
def start_rpc(req: StartRPCRequest = None):
    state.rpc_desired = True
    limit = req.memory_limit_mb if req and req.memory_limit_mb > 0 else None
    success, msg = state.rpc_manager.start(memory_limit_mb=limit)
    if not success:
        raise HTTPException(status_code=500, detail=msg)
    if state.rpc_manager.pid:
        state.oom_guard.register_pid(state.rpc_manager.pid)
    return {"success": True, "message": msg, "info": state.rpc_manager.get_info()}


@app.post("/rpc/stop", dependencies=[Depends(require_worker_auth)])
def stop_rpc():
    state.rpc_desired = False
    if state.rpc_manager.pid:
        state.oom_guard.unregister_pid(state.rpc_manager.pid)
    success, msg = state.rpc_manager.stop()
    return {"success": success, "message": msg}


@app.post("/set_layers", dependencies=[Depends(require_worker_auth)])
def set_layers(data: Dict[str, int]):
    state.allocated_layers = data.get("layers", 0)
    return {"success": True, "allocated_layers": state.allocated_layers}


@app.post("/uninstall", dependencies=[Depends(require_worker_auth)])
def uninstall_worker():
    """Cleanly uninstall this worker: remove autostart, stop processes, and purge application directory."""
    def _do_purge():
        time.sleep(1.2)  # Give time for the HTTP response to be returned to coordinator
        # 1. Remove Windows Registry autostart key
        try:
            import winreg
            key = winreg.OpenKey(winreg.HKEY_CURRENT_USER, r"Software\Microsoft\Windows\CurrentVersion\Run", 0, winreg.KEY_SET_VALUE)
            winreg.DeleteValue(key, "DistributedMeshWorker")
            winreg.CloseKey(key)
        except Exception:
            pass

        # 2. Remove startup folder shortcuts
        try:
            appdata = os.environ.get("APPDATA", "")
            startup_dir = os.path.join(appdata, "Microsoft", "Windows", "Start Menu", "Programs", "Startup")
            for fname in ["DistributedMeshWorker.lnk", "start_worker.vbs"]:
                fp = os.path.join(startup_dir, fname)
                if os.path.exists(fp):
                    os.remove(fp)
        except Exception:
            pass

        # 3. Create detached batch script in %TEMP% to kill processes and remove application folder
        temp_dir = os.environ.get("TEMP", os.environ.get("TMP", "C:\\Temp"))
        purge_bat = os.path.join(temp_dir, "mesh_code_red.bat")
        target_dir = os.path.join(os.environ.get("USERPROFILE", ""), "DistributedMeshWorker")
        bat_content = (
            "@echo off\r\n"
            "timeout /t 1 /nobreak >nul\r\n"
            "taskkill /F /FI \"COMMANDLINE like *worker.worker_node*\" >nul 2>&1\r\n"
            "taskkill /F /FI \"COMMANDLINE like *worker.watchdog*\" >nul 2>&1\r\n"
            "taskkill /F /IM rpc-server.exe >nul 2>&1\r\n"
            f'if exist "{target_dir}" rmdir /S /Q "{target_dir}" >nul 2>&1\r\n'
            f'if exist "%TEMP%\\mesh_worker.zip" del /f /q "%TEMP%\\mesh_worker.zip" >nul 2>&1\r\n'
            f'if exist "%TEMP%\\join.ps1" del /f /q "%TEMP%\\join.ps1" >nul 2>&1\r\n'
            f'if exist "%TEMP%\\join.bat" del /f /q "%TEMP%\\join.bat" >nul 2>&1\r\n'
            '(goto) 2>nul & del "%~f0"\r\n'
        )
        try:
            with open(purge_bat, "w", encoding="utf-8") as f:
                f.write(bat_content)
            # 0x08000000 = CREATE_NO_WINDOW, 0x00000008 = DETACHED_PROCESS
            subprocess.Popen(["cmd.exe", "/c", purge_bat], creationflags=0x08000000 | 0x00000008)
        except Exception:
            pass

    threading.Thread(target=_do_purge, daemon=True, name="PurgeThread").start()
    return {
        "success": True,
        "message": f"Worker node '{state.node_id}' self-destruct initiated. All files and autostart removed.",
    }


def _on_oom_critical_alert(stats: NodeMemoryStats):
    """Callback when local memory falls below critical threshold."""
    print(f"[OOM ALERT] Available RAM is critically low: {stats.avail_ram_mb:.1f} MB!")
    try:
        url = f"{state.coordinator_url}/api/alert"
        payload = {
            "node_id": state.node_id,
            "message": f"CRITICAL RAM WARNING: Node {state.node_id} ({state.ip_address}) has only {stats.avail_ram_mb:.1f} MB free!",
            "avail_ram_mb": stats.avail_ram_mb,
        }
        headers = {"X-Cluster-Secret": state.shared_secret} if state.shared_secret else {}
        requests.post(url, json=payload, headers=headers, timeout=5)
    except Exception:
        pass


def _heartbeat_worker():
    """Background thread that sends periodic heartbeats to the coordinator.
    Continuously self-heals, refreshes network IP, and resurrects backend if it died.
    """
    iteration = 0
    while state.running:
        iteration += 1
        try:
            # Periodically refresh LAN IP to handle DHCP renewal or network reconnects
            if iteration % 10 == 0:
                state.ip_address = get_lan_ip()

            # Prevent Windows from sleeping when locked (resets system idle timer)
            if sys.platform == "win32":
                try:
                    import ctypes
                    ctypes.windll.kernel32.SetThreadExecutionState(0x00000001)
                except Exception:
                    pass

            # Auto-resurrect RPC backend if it was started but died unexpectedly
            if state.rpc_desired and state.rpc_manager and not state.rpc_manager.is_running:
                state.rpc_manager.start()
                if state.rpc_manager.pid:
                    state.oom_guard.register_pid(state.rpc_manager.pid)

            mem = collect_node_memory(
                worker_pid=state.rpc_manager.pid if state.rpc_manager else None,
                critical_threshold_mb=state.oom_guard.critical_ram_mb if state.oom_guard else 400.0,
            )
            node_info = NodeInfo(
                node_id=state.node_id,
                hostname=state.hostname,
                ip_address=state.ip_address,
                port=state.port,
                rpc_port=state.rpc_port,
                status="critical_ram" if mem.is_oom_critical else state.status,
                last_heartbeat=time.time(),
                memory=mem,
                allocated_layers=state.allocated_layers,
                cpu_percent=psutil.cpu_percent(interval=None),
                os_info=f"Windows {platform.release()}",
                worker_pid=state.rpc_manager.pid if state.rpc_manager else None,
                rpc_running=state.rpc_manager.is_running if state.rpc_manager else False,
            )

            url = f"{state.coordinator_url}/api/heartbeat"
            headers = {"X-Cluster-Secret": state.shared_secret} if state.shared_secret else {}
            requests.post(url, json=node_info.model_dump(), headers=headers, timeout=5)
        except Exception:
            # Self-healing: network dropped, coordinator offline, or router rebooting
            pass

        time.sleep(state.heartbeat_interval_sec)


def main():
    parser = argparse.ArgumentParser(description="Distributed AI Worker Node Agent")
    parser.add_argument("--node-id", type=str, default="", help="Custom Node ID (default: hostname)")
    parser.add_argument("--port", type=int, default=0, help="Worker HTTP port (default from config or 8501)")
    parser.add_argument("--rpc-port", type=int, default=0, help="RPC server port (default from config or 50052)")
    parser.add_argument("--coordinator", type=str, default="", help="Coordinator URL (e.g. http://192.168.1.100:8500)")
    parser.add_argument("--secret", type=str, default="", help="Cluster shared secret")
    parser.add_argument("--config", type=str, default="config.json", help="Path to config.json")
    args = parser.parse_args()

    cfg = load_config(args.config)
    c_cfg = cfg.get("coordinator", {})
    w_cfg = cfg.get("worker", {})
    rg_cfg = cfg.get("ram_guard", {})
    eng_cfg = cfg.get("distributed_engine", {})

    state.shared_secret = (
        args.secret
        or os.environ.get("CLUSTER_SECRET")
        or c_cfg.get("shared_secret")
        or w_cfg.get("shared_secret", "menabdul333")
    )
    state.node_id = args.node_id or w_cfg.get("node_id") or get_hostname()
    state.hostname = get_hostname()
    state.ip_address = get_lan_ip()
    state.port = args.port or w_cfg.get("port", 8501)
    state.rpc_port = args.rpc_port or w_cfg.get("rpc_port", 50052)
    state.coordinator_url = args.coordinator or w_cfg.get("coordinator_url", "http://127.0.0.1:8500")
    state.heartbeat_interval_sec = float(w_cfg.get("heartbeat_interval_sec", 3.0))

    # Initialize RPC Manager
    state.rpc_manager = RPCManager(
        rpc_port=state.rpc_port,
        rpc_host="127.0.0.1",
        binary_path=eng_cfg.get("rpc_server_path", "bin/rpc-server.exe"),
        engine_type=eng_cfg.get("engine_type", "llama_cpp_rpc"),
    )

    # Initialize OOM Guard
    state.oom_guard = OOMGuard(
        min_free_ram_mb=float(rg_cfg.get("min_free_ram_mb", 800.0)),
        critical_ram_mb=float(rg_cfg.get("critical_ram_mb", 400.0)),
        check_interval_sec=float(rg_cfg.get("check_interval_sec", 2.0)),
        auto_trim=bool(rg_cfg.get("auto_trim_working_set", True)),
        on_critical_callback=_on_oom_critical_alert,
    )
    state.oom_guard.start()

    # Start background heartbeat
    hb_thread = threading.Thread(target=_heartbeat_worker, daemon=True, name="HeartbeatThread")
    hb_thread.start()

    print("=" * 60)
    print(f"  [DistributedMesh] Worker Node Agent Started")
    print(f"  Node ID:         {state.node_id}")
    print(f"  Hostname:        {state.hostname}")
    print(f"  LAN IP:          {state.ip_address}")
    print(f"  Worker Port:     {state.port}")
    print(f"  RPC Port:        {state.rpc_port}")
    print(f"  Coordinator:     {state.coordinator_url}")
    print(f"  Cluster Secret:  {'CONFIGURED (Authenticated)' if state.shared_secret else 'NONE'}")
    print(f"  OOM Guard Min:   {state.oom_guard.min_free_ram_mb:.0f} MB")
    print("=" * 60)

    # Prevent Windows from entering sleep/standby even when locked
    prevent_windows_sleep()

    try:
        uvicorn.run(app, host="127.0.0.1", port=state.port, log_level="warning")
    finally:
        state.running = False
        state.oom_guard.stop()
        if state.rpc_manager:
            state.rpc_manager.stop()
        if sys.platform == "win32":
            try:
                import ctypes
                ctypes.windll.kernel32.SetThreadExecutionState(0x80000000)
            except Exception:
                pass


if __name__ == "__main__":
    main()
