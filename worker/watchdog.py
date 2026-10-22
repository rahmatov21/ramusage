"""Continuous background watchdog supervisor for worker node.
Ensures worker runs 24/7 completely in the background with zero visible windows.
"""

import os
import signal
import subprocess
import sys
import time
from pathlib import Path


def run_watchdog():
    base_dir = Path(__file__).resolve().parent.parent
    logs_dir = base_dir / "logs"
    logs_dir.mkdir(exist_ok=True)
    log_file = logs_dir / "worker.log"
    pid_file = base_dir / "worker.pid"

    # Write supervisor PID
    pid_file.write_text(str(os.getpid()), encoding="utf-8")

    # Detect pythonw.exe for silent execution
    python_dir = Path(sys.executable).parent
    pythonw = python_dir / "pythonw.exe"
    exe = str(pythonw) if pythonw.is_file() else sys.executable

    def _cleanup(*args):
        try:
            if pid_file.is_file():
                pid_file.unlink()
        except Exception:
            pass
        sys.exit(0)

    try:
        signal.signal(signal.SIGTERM, _cleanup)
        signal.signal(signal.SIGINT, _cleanup)
    except Exception:
        pass

    with open(log_file, "a", encoding="utf-8") as log:
        log.write(f"\n========================================================\n")
        log.write(f"[{time.strftime('%Y-%m-%d %H:%M:%S')}] DistributedMesh Worker Background Watchdog Started (PID {os.getpid()})\n")
        log.write(f"Executing: {exe} -m worker.worker_node\n")
        log.write(f"========================================================\n")
        log.flush()

        while True:
            try:
                cmd = [exe, "-m", "worker.worker_node"]
                if len(sys.argv) > 1:
                    cmd.extend(sys.argv[1:])

                proc = subprocess.Popen(
                    cmd,
                    cwd=str(base_dir),
                    stdout=log,
                    stderr=log,
                    creationflags=subprocess.CREATE_NO_WINDOW if os.name == "nt" else 0,
                )

                proc.wait()
                log.write(f"[{time.strftime('%Y-%m-%d %H:%M:%S')}] Worker process (PID {proc.pid}) exited with code {proc.returncode}. Respawning in 2s...\n")
                log.flush()
            except Exception as e:
                log.write(f"[{time.strftime('%Y-%m-%d %H:%M:%S')}] Watchdog error: {e}. Retrying in 2s...\n")
                log.flush()

            time.sleep(2)


if __name__ == "__main__":
    run_watchdog()
