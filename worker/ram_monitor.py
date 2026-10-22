"""Zero-admin Windows Memory Monitor & OOM Guard.
Leverages ctypes Win32 API and psutil to monitor and manage RAM/VRAM.
"""

import ctypes
from ctypes import wintypes
import gc
import os
import shutil
import subprocess
import threading
import time
from typing import Callable, List, Optional, Tuple

import psutil
from common.models import NodeMemoryStats


# --- Win32 ctypes structure for GlobalMemoryStatusEx ---
class MEMORYSTATUSEX(ctypes.Structure):
    _fields_ = [
        ("dwLength", wintypes.DWORD),
        ("dwMemoryLoad", wintypes.DWORD),
        ("ullTotalPhys", ctypes.c_uint64),
        ("ullAvailPhys", ctypes.c_uint64),
        ("ullTotalPageFile", ctypes.c_uint64),
        ("ullAvailPageFile", ctypes.c_uint64),
        ("ullTotalVirtual", ctypes.c_uint64),
        ("ullAvailVirtual", ctypes.c_uint64),
        ("ullAvailExtendedVirtual", ctypes.c_uint64),
    ]


def _get_win32_ram_stats() -> Tuple[float, float, float, float, float, float]:
    """Retrieve exact physical and pagefile memory using Win32 API (MB).
    Requires zero administrator privileges.
    Returns: (total_ram_mb, avail_ram_mb, used_ram_mb, percent, swap_total_mb, swap_avail_mb)
    """
    if os.name == "nt":
        try:
            stat = MEMORYSTATUSEX()
            stat.dwLength = ctypes.sizeof(MEMORYSTATUSEX)
            if ctypes.windll.kernel32.GlobalMemoryStatusEx(ctypes.byref(stat)):
                mb = 1024 * 1024
                total_ram = stat.ullTotalPhys / mb
                avail_ram = stat.ullAvailPhys / mb
                used_ram = total_ram - avail_ram
                percent = float(stat.dwMemoryLoad)
                swap_total = stat.ullTotalPageFile / mb
                swap_avail = stat.ullAvailPageFile / mb
                return total_ram, avail_ram, used_ram, percent, swap_total, swap_avail
        except Exception:
            pass

    # Fallback to psutil
    vm = psutil.virtual_memory()
    sm = psutil.swap_memory()
    mb = 1024 * 1024
    return (
        vm.total / mb,
        vm.available / mb,
        vm.used / mb,
        vm.percent,
        sm.total / mb,
        sm.free / mb,
    )


def _get_vram_stats() -> Tuple[Optional[float], Optional[float]]:
    """Detect GPU VRAM using nvidia-smi if available (MB).
    Returns (total_vram_mb, free_vram_mb) or (None, None).
    """
    if shutil.which("nvidia-smi"):
        try:
            res = subprocess.run(
                ["nvidia-smi", "--query-gpu=memory.total,memory.free", "--format=csv,noheader,nounits"],
                capture_output=True,
                text=True,
                timeout=2,
            )
            if res.returncode == 0 and res.stdout.strip():
                line = res.stdout.strip().splitlines()[0]
                parts = [p.strip() for p in line.split(",")]
                if len(parts) >= 2:
                    return float(parts[0]), float(parts[1])
        except Exception:
            pass
    return None, None


def trim_process_memory(pid: Optional[int] = None) -> bool:
    """Trim working set pages of a process to free unused memory back to standby list.
    Works for any process owned by the current user (NO admin rights required).
    """
    if pid is None:
        pid = os.getpid()

    # First invoke Python garbage collection if self
    if pid == os.getpid():
        gc.collect()

    if os.name == "nt":
        PROCESS_QUERY_INFORMATION = 0x0400
        PROCESS_SET_QUOTA = 0x0100
        try:
            handle = ctypes.windll.kernel32.OpenProcess(
                PROCESS_QUERY_INFORMATION | PROCESS_SET_QUOTA, False, pid
            )
            if handle:
                res = ctypes.windll.psapi.EmptyWorkingSet(handle)
                ctypes.windll.kernel32.CloseHandle(handle)
                return bool(res)
        except Exception:
            return False
    return False


def trim_all_worker_memory(pids: List[int]) -> int:
    """Trim working set for multiple PIDs including current process."""
    success_count = 0
    all_pids = set(pids) | {os.getpid()}
    for pid in all_pids:
        if trim_process_memory(pid):
            success_count += 1
    return success_count


def get_process_ram_mb(pid: Optional[int] = None) -> float:
    """Get resident set size / working set of a process in MB."""
    if pid is None:
        pid = os.getpid()
    try:
        proc = psutil.Process(pid)
        return proc.memory_info().rss / (1024 * 1024)
    except Exception:
        return 0.0


def collect_node_memory(worker_pid: Optional[int] = None, critical_threshold_mb: float = 400.0) -> NodeMemoryStats:
    """Collect complete snapshot of node memory."""
    total_ram, avail_ram, used_ram, percent, swap_tot, swap_avail = _get_win32_ram_stats()
    vram_tot, vram_free = _get_vram_stats()

    proc_ram = 0.0
    if worker_pid:
        proc_ram += get_process_ram_mb(worker_pid)
    proc_ram += get_process_ram_mb(os.getpid())

    is_oom = avail_ram <= critical_threshold_mb

    return NodeMemoryStats(
        total_ram_mb=round(total_ram, 1),
        avail_ram_mb=round(avail_ram, 1),
        used_ram_mb=round(used_ram, 1),
        percent_used=round(percent, 1),
        swap_total_mb=round(swap_tot, 1),
        swap_avail_mb=round(swap_avail, 1),
        vram_total_mb=round(vram_tot, 1) if vram_tot else None,
        vram_free_mb=round(vram_free, 1) if vram_free else None,
        process_ram_mb=round(proc_ram, 1),
        is_oom_critical=is_oom,
    )


class OOMGuard:
    """Active background watcher protecting node from Windows Out-Of-Memory thrashing."""

    def __init__(
        self,
        min_free_ram_mb: float = 800.0,
        critical_ram_mb: float = 400.0,
        check_interval_sec: float = 2.0,
        auto_trim: bool = True,
        on_critical_callback: Optional[Callable[[NodeMemoryStats], None]] = None,
    ):
        self.min_free_ram_mb = min_free_ram_mb
        self.critical_ram_mb = critical_ram_mb
        self.check_interval_sec = check_interval_sec
        self.auto_trim = auto_trim
        self.on_critical_callback = on_critical_callback

        self._monitored_pids: List[int] = []
        self._running = False
        self._thread: Optional[threading.Thread] = None
        self._last_alert_time = 0.0
        self.alert_cooldown_sec = 15.0

    def register_pid(self, pid: int) -> None:
        """Register a worker process PID to watch and trim."""
        if pid not in self._monitored_pids:
            self._monitored_pids.append(pid)

    def unregister_pid(self, pid: int) -> None:
        """Remove a PID from monitoring."""
        if pid in self._monitored_pids:
            self._monitored_pids.remove(pid)

    def start(self) -> None:
        """Start the background guard thread."""
        if self._running:
            return
        self._running = True
        self._thread = threading.Thread(target=self._guard_loop, daemon=True, name="OOMGuardThread")
        self._thread.start()

    def stop(self) -> None:
        """Stop the background guard thread."""
        self._running = False
        if self._thread:
            self._thread.join(timeout=1.0)

    def _guard_loop(self) -> None:
        while self._running:
            try:
                stats = collect_node_memory(critical_threshold_mb=self.critical_ram_mb)
                now = time.time()

                if stats.avail_ram_mb < self.min_free_ram_mb:
                    # Low memory detected
                    if self.auto_trim:
                        trim_all_worker_memory(self._monitored_pids)

                    # Trigger alert callback if below critical threshold
                    if stats.avail_ram_mb < self.critical_ram_mb:
                        if (now - self._last_alert_time) >= self.alert_cooldown_sec:
                            self._last_alert_time = now
                            if self.on_critical_callback:
                                self.on_critical_callback(stats)
            except Exception:
                pass
            time.sleep(self.check_interval_sec)
