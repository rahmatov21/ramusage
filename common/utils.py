"""Utility functions for network discovery, configuration, and formatting."""

import json
import os
import socket
from pathlib import Path
from typing import Any, Dict


def get_lan_ip() -> str:
    """Detect the local LAN IP address of this machine.
    Works entirely in user space without requiring administrator privileges.
    """
    s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    try:
        # Doesn't actually send packets over the network, just queries the OS routing table
        s.connect(("10.255.255.255", 1))
        ip = s.getsockname()[0]
    except Exception:
        try:
            ip = socket.gethostbyname(socket.gethostname())
        except Exception:
            ip = "127.0.0.1"
    finally:
        s.close()
    return ip


def get_hostname() -> str:
    """Get the machine's netbios/DNS hostname."""
    try:
        return socket.gethostname()
    except Exception:
        return "UnknownHost"


def format_mb(mb: float) -> str:
    """Format megabytes into human-readable MB or GB string."""
    if mb >= 1024:
        return f"{mb / 1024:.2f} GB"
    return f"{mb:.1f} MB"


def format_bar(percent: float, width: int = 10) -> str:
    """Create a text progress bar for CLI and Telegram displays."""
    percent = max(0.0, min(100.0, percent))
    filled = int(round(width * (percent / 100.0)))
    empty = width - filled
    return "█" * filled + "░" * empty


def load_config(config_path: str = "config.json") -> Dict[str, Any]:
    """Load configuration from config.json with fallback defaults."""
    default_config: Dict[str, Any] = {
        "cluster_name": "DistributedMesh-AI",
        "coordinator": {
            "host": "0.0.0.0",
            "port": 8500,
            "shared_secret": "neuro_mesh_secret_2026"
        },
        "worker": {
            "node_id": "",
            "port": 8501,
            "rpc_port": 50052,
            "coordinator_url": "http://127.0.0.1:8500",
            "heartbeat_interval_sec": 3
        },
        "ram_guard": {
            "min_free_ram_mb": 800,
            "critical_ram_mb": 400,
            "reserve_buffer_mb": 1200,
            "auto_trim_working_set": True,
            "check_interval_sec": 2
        },
        "telegram": {
            "enabled": False,
            "bot_token": "",
            "authorized_chat_ids": []
        },
        "distributed_engine": {
            "engine_type": "llama_cpp_rpc",
            "rpc_server_path": "bin/rpc-server.exe",
            "default_model_layers": 32,
            "model_name": "Llama-3-8B-Q4_K_M"
        }
    }

    path = Path(config_path)
    if not path.is_file():
        # Fall back to config.example.json if config.json not yet created
        example_path = Path("config.example.json")
        if example_path.is_file():
            path = example_path

    if path.is_file():
        try:
            with open(path, "r", encoding="utf-8") as f:
                user_config = json.load(f)
                # Deep merge top-level sections
                for key, val in user_config.items():
                    if isinstance(val, dict) and key in default_config and isinstance(default_config[key], dict):
                        default_config[key].update(val)
                    else:
                        default_config[key] = val
        except Exception as e:
            print(f"[WARN] Error reading config file {path}: {e}. Using defaults.")

    return default_config


def save_config(config_data: Dict[str, Any], config_path: str = "config.json") -> bool:
    """Save configuration safely to json file."""
    try:
        with open(config_path, "w", encoding="utf-8") as f:
            json.dump(config_data, f, indent=2)
        return True
    except Exception as e:
        print(f"[ERROR] Failed to save config: {e}")
        return False
