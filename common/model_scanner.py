"""Pure-Python zero-dependency GGUF header reader and model scanner.
Extracts model architecture, layer count, and quantization from local files.
"""

import json
import os
import struct
from pathlib import Path
from typing import Any, Dict, List, Optional
from pydantic import BaseModel


class LocalModelInfo(BaseModel):
    model_config = {"protected_namespaces": ()}
    model_id: str
    name: str
    filename: str
    file_path: str
    size_mb: float
    size_gb: float
    architecture: str = "llama"
    layers: int = 32
    quantization: str = "Unknown"
    source: str = "Local"  # "LM Studio", "Ollama", "HuggingFace", "Custom"
    node_id: str = ""


# GGUF Value Types
GGUF_TYPE_UINT8 = 0
GGUF_TYPE_INT8 = 1
GGUF_TYPE_UINT16 = 2
GGUF_TYPE_INT16 = 3
GGUF_TYPE_UINT32 = 4
GGUF_TYPE_INT32 = 5
GGUF_TYPE_FLOAT32 = 6
GGUF_TYPE_BOOL = 7
GGUF_TYPE_STRING = 8
GGUF_TYPE_ARRAY = 9
GGUF_TYPE_UINT64 = 10
GGUF_TYPE_INT64 = 11
GGUF_TYPE_FLOAT64 = 12


def _read_gguf_string(f) -> str:
    len_bytes = f.read(8)
    if len(len_bytes) < 8:
        return ""
    length = struct.unpack("<Q", len_bytes)[0]
    if length > 1024 * 1024:  # Safety sanity check
        return ""
    str_bytes = f.read(length)
    return str_bytes.decode("utf-8", errors="ignore")


def inspect_gguf_file(path: str) -> Optional[Dict[str, Any]]:
    """Read GGUF header metadata without loading model weights into memory."""
    try:
        with open(path, "rb") as f:
            magic = f.read(4)
            if magic != b"GGUF":
                return None

            version = struct.unpack("<I", f.read(4))[0]
            if version > 10:
                return None

            tensor_count = struct.unpack("<Q", f.read(8))[0]
            metadata_count = struct.unpack("<Q", f.read(8))[0]

            metadata: Dict[str, Any] = {
                "version": version,
                "tensors": tensor_count,
            }

            # Read top metadata keys (limit to first 120 keys to stay fast)
            keys_to_read = min(120, metadata_count)
            for _ in range(keys_to_read):
                key = _read_gguf_string(f)
                if not key:
                    break

                val_type_bytes = f.read(4)
                if len(val_type_bytes) < 4:
                    break
                val_type = struct.unpack("<I", val_type_bytes)[0]

                if val_type == GGUF_TYPE_STRING:
                    val = _read_gguf_string(f)
                    metadata[key] = val
                elif val_type == GGUF_TYPE_UINT32:
                    val = struct.unpack("<I", f.read(4))[0]
                    metadata[key] = val
                elif val_type == GGUF_TYPE_INT32:
                    val = struct.unpack("<i", f.read(4))[0]
                    metadata[key] = val
                elif val_type == GGUF_TYPE_UINT64:
                    val = struct.unpack("<Q", f.read(8))[0]
                    metadata[key] = val
                elif val_type == GGUF_TYPE_INT64:
                    val = struct.unpack("<q", f.read(8))[0]
                    metadata[key] = val
                elif val_type == GGUF_TYPE_BOOL:
                    val = bool(struct.unpack("<B", f.read(1))[0])
                    metadata[key] = val
                elif val_type == GGUF_TYPE_FLOAT32:
                    val = struct.unpack("<f", f.read(4))[0]
                    metadata[key] = val
                else:
                    # Skip other complex/array types to avoid parsing the whole file
                    break

            return metadata
    except Exception:
        return None


def get_lm_studio_models_dir() -> Optional[str]:
    """Auto-detect LM Studio downloads folder from settings.json or default location."""
    user_home = Path.home()
    settings_file = user_home / ".lmstudio" / "settings.json"
    if settings_file.is_file():
        try:
            with open(settings_file, "r", encoding="utf-8") as f:
                data = json.load(f)
                folder = data.get("downloadsFolder")
                if folder and os.path.isdir(folder):
                    return folder
        except Exception:
            pass

    # Standard default candidates
    candidates = [
        user_home / ".lmstudio" / "models",
        user_home / ".cache" / "lm-studio" / "models",
    ]
    for c in candidates:
        if c.is_dir():
            return str(c)
    return None


def scan_local_models(custom_paths: Optional[List[str]] = None, node_id: str = "") -> List[LocalModelInfo]:
    """Scan LM Studio, Ollama, HuggingFace, and local model directories."""
    directories_to_scan: List[tuple[str, str]] = []

    # 1. LM Studio
    lm_dir = get_lm_studio_models_dir()
    if lm_dir:
        directories_to_scan.append((lm_dir, "LM Studio"))

    # 2. Local project models directory
    local_proj_models = Path("models").resolve()
    if local_proj_models.is_dir():
        directories_to_scan.append((str(local_proj_models), "Local Project"))

    # 3. Custom paths from config
    if custom_paths:
        for p in custom_paths:
            if os.path.isdir(p):
                directories_to_scan.append((p, "Custom Folder"))

    found_models: List[LocalModelInfo] = []
    seen_paths = set()

    for folder_path, source in directories_to_scan:
        try:
            for root, _, files in os.walk(folder_path):
                for file in files:
                    if file.lower().endswith((".gguf", ".bin", ".safetensors")):
                        full_path = os.path.join(root, file)
                        if full_path in seen_paths:
                            continue
                        seen_paths.add(full_path)

                        try:
                            stat = os.stat(full_path)
                            size_mb = stat.st_size / (1024 * 1024)
                            size_gb = stat.st_size / (1024 * 1024 * 1024)
                        except Exception:
                            continue

                        # Extract metadata if GGUF
                        arch = "llama"
                        layers = 32
                        quant = "Unknown"

                        if file.lower().endswith(".gguf"):
                            meta = inspect_gguf_file(full_path)
                            if meta:
                                arch = meta.get("general.architecture", "llama")
                                # Try block_count keys
                                for k, v in meta.items():
                                    if k.endswith(".block_count") and isinstance(v, int):
                                        layers = v
                                        break
                                # Quantization guess from filename or meta
                                for q in ["Q4_K_M", "Q4_0", "Q4_K_S", "Q5_K_M", "Q5_0", "Q8_0", "F16", "Q3_K_M"]:
                                    if q.lower() in file.lower():
                                        quant = q
                                        break

                        # Estimate layers if not detected
                        if layers == 32:
                            if size_gb > 25:
                                layers = 80  # 70B
                            elif size_gb > 12:
                                layers = 48  # 30B / 34B
                            elif size_gb > 7:
                                layers = 40  # 14B

                        name = Path(file).stem
                        model_id = f"{node_id}_{name}" if node_id else name

                        found_models.append(
                            LocalModelInfo(
                                model_id=model_id,
                                name=name,
                                filename=file,
                                file_path=full_path,
                                size_mb=round(size_mb, 1),
                                size_gb=round(size_gb, 2),
                                architecture=arch,
                                layers=layers,
                                quantization=quant,
                                source=source,
                                node_id=node_id,
                            )
                        )
        except Exception:
            pass

    return found_models
