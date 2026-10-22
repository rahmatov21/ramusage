"""Background worker status checker."""
import json
import psutil
import requests
from pathlib import Path


def check_status():
    procs = []
    for p in psutil.process_iter(['pid', 'name', 'cmdline', 'memory_info']):
        try:
            cmd = " ".join(p.info['cmdline'] or [])
            if 'worker.worker_node' in cmd or 'worker.watchdog' in cmd:
                procs.append({
                    "pid": p.info['pid'],
                    "name": p.info['name'],
                    "ram_mb": round(p.info['memory_info'].rss / (1024 * 1024), 1)
                })
        except Exception:
            pass

    if procs:
        print("  [STATUS: ACTIVE - 24/7 BACKGROUND]")
        for proc in procs:
            print(f"  * {proc['name']} (PID {proc['pid']}) | RAM: {proc['ram_mb']} MB")

        try:
            r = requests.get("http://127.0.0.1:8501/status", timeout=2)
            if r.status_code == 200:
                data = r.json()
                avail_ram = round(data.get("memory", {}).get("avail_ram_mb", 0.0))
                print(f"  * Local Worker API: ONLINE | Node ID: {data.get('node_id')} | Free RAM: {avail_ram} MB")
        except Exception:
            print("  * Local Worker API: Initializing...")
    else:
        print("  [STATUS: STOPPED - Not running]")


if __name__ == "__main__":
    check_status()
