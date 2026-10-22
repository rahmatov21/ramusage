"""Process manager for local inference backend (llama.cpp rpc-server or Python worker).
Runs in user space without requiring administrator privileges.
"""

import os
import shutil
import subprocess
import sys
import threading
import time
from typing import Dict, Optional, Tuple


class RPCManager:
    """Manages the lifecycle of the local RPC inference backend."""

    def __init__(
        self,
        rpc_port: int = 50052,
        rpc_host: str = "0.0.0.0",
        binary_path: str = "bin/rpc-server.exe",
        engine_type: str = "llama_cpp_rpc",
    ):
        self.rpc_port = rpc_port
        self.rpc_host = rpc_host
        self.binary_path = binary_path
        self.engine_type = engine_type
        self.process: Optional[subprocess.Popen] = None
        self._lock = threading.Lock()
        self._mode = "idle"  # "llama_rpc", "python_fallback", "idle"

    @property
    def is_running(self) -> bool:
        """Check if backend process is actively running."""
        with self._lock:
            if self.process is not None:
                poll = self.process.poll()
                return poll is None
            return False

    @property
    def pid(self) -> Optional[int]:
        """Return PID of running worker if active."""
        with self._lock:
            if self.process and self.process.poll() is None:
                return self.process.pid
            return None

    def start(self, memory_limit_mb: Optional[float] = None) -> Tuple[bool, str]:
        """Start the RPC inference backend."""
        with self._lock:
            if self.process and self.process.poll() is None:
                return True, f"RPC worker already running on PID {self.process.pid}"

            # Check if rpc-server binary exists
            bin_path = None
            if os.path.isfile(self.binary_path):
                bin_path = self.binary_path
            elif os.path.isfile(os.path.basename(self.binary_path)):
                bin_path = os.path.basename(self.binary_path)
            elif shutil.which("rpc-server"):
                bin_path = "rpc-server"

            if bin_path:
                try:
                    cmd = [
                        bin_path,
                        "-H", self.rpc_host,
                        "-p", str(self.rpc_port),
                    ]
                    if memory_limit_mb:
                        # llama.cpp rpc-server supports memory reservation in MB/GB
                        cmd.extend(["-m", str(int(memory_limit_mb * 1024 * 1024))])

                    self.process = subprocess.Popen(
                        cmd,
                        stdout=subprocess.DEVNULL,
                        stderr=subprocess.DEVNULL,
                        creationflags=subprocess.CREATE_NO_WINDOW if os.name == "nt" else 0,
                    )
                    self._mode = "llama_rpc"
                    return True, f"Started llama.cpp RPC server on port {self.rpc_port} (PID {self.process.pid})"
                except Exception as e:
                    return False, f"Failed to start {bin_path}: {e}"

            # Fallback: start lightweight built-in Python RPC simulator
            try:
                cmd = [
                    sys.executable,
                    "-m",
                    "worker.mock_rpc_server",
                    "--host",
                    self.rpc_host,
                    "--port",
                    str(self.rpc_port),
                ]
                self.process = subprocess.Popen(
                    cmd,
                    stdout=subprocess.DEVNULL,
                    stderr=subprocess.DEVNULL,
                    creationflags=subprocess.CREATE_NO_WINDOW if os.name == "nt" else 0,
                )
                self._mode = "python_fallback"
                return True, f"Started fallback RPC agent on port {self.rpc_port} (PID {self.process.pid})"
            except Exception as e:
                return False, f"Failed to start Python fallback RPC: {e}"

    def stop(self) -> Tuple[bool, str]:
        """Gracefully terminate the worker process."""
        with self._lock:
            if not self.process or self.process.poll() is not None:
                self.process = None
                self._mode = "idle"
                return True, "RPC worker is not running"

            try:
                self.process.terminate()
                try:
                    self.process.wait(timeout=3)
                except subprocess.TimeoutExpired:
                    self.process.kill()
                    self.process.wait(timeout=2)
                pid = self.process.pid
                self.process = None
                self._mode = "idle"
                return True, f"Stopped RPC worker (PID {pid})"
            except Exception as e:
                return False, f"Error stopping RPC worker: {e}"

    def get_info(self) -> Dict[str, object]:
        """Get summary info about RPC process."""
        return {
            "running": self.is_running,
            "pid": self.pid,
            "port": self.rpc_port,
            "mode": self._mode,
        }
