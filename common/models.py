"""Data models for cluster state, memory stats, and RPC communication."""

from typing import Dict, List, Optional
from pydantic import BaseModel, Field
import time


class NodeMemoryStats(BaseModel):
    """Memory statistics for a single worker node."""
    total_ram_mb: float = Field(..., description="Total physical RAM in MB")
    avail_ram_mb: float = Field(..., description="Available physical RAM in MB")
    used_ram_mb: float = Field(..., description="Used physical RAM in MB")
    percent_used: float = Field(..., description="Percentage of RAM used (0-100)")
    swap_total_mb: float = Field(0.0, description="Total pagefile / swap in MB")
    swap_avail_mb: float = Field(0.0, description="Available pagefile / swap in MB")
    vram_total_mb: Optional[float] = Field(None, description="Total VRAM in MB if GPU detected")
    vram_free_mb: Optional[float] = Field(None, description="Free VRAM in MB if GPU detected")
    process_ram_mb: float = Field(0.0, description="RAM consumed by local worker process in MB")
    is_oom_critical: bool = Field(False, description="True if available RAM is below critical safety threshold")


class NodeInfo(BaseModel):
    """Metadata and live status of a worker node."""
    node_id: str
    hostname: str
    ip_address: str
    port: int
    rpc_port: int
    status: str = "online"  # online, idle, busy, critical_ram, offline
    last_heartbeat: float = Field(default_factory=time.time)
    memory: NodeMemoryStats
    allocated_layers: int = 0
    cpu_percent: float = 0.0
    os_info: str = "Windows"
    worker_pid: Optional[int] = None
    rpc_running: bool = False


class LayerAllocation(BaseModel):
    """Layer split assignment for a specific node."""
    node_id: str
    ip_address: str
    rpc_port: int
    layers: int
    start_layer: int
    end_layer: int
    usable_ram_mb: float
    assigned_ram_mb: float


class ClusterSplitPlan(BaseModel):
    """Cluster-wide distribution plan for a target AI model."""
    model_config = {"protected_namespaces": ()}
    model_name: str
    total_layers: int
    total_available_ram_mb: float
    allocations: List[LayerAllocation] = []
    rpc_endpoints: List[str] = []
    is_viable: bool = True
    warnings: List[str] = []


class ClusterStatus(BaseModel):
    """Full cluster snapshot maintained by the coordinator."""
    model_config = {"protected_namespaces": ()}
    cluster_name: str
    nodes: Dict[str, NodeInfo] = {}
    total_cluster_ram_gb: float = 0.0
    free_cluster_ram_gb: float = 0.0
    total_nodes: int = 0
    online_nodes: int = 0
    active_model: Optional[str] = None
    layer_distribution: Dict[str, int] = {}
    last_updated: float = Field(default_factory=time.time)


class InferenceRequest(BaseModel):
    """Inference prompt dispatched to the cluster."""
    model_config = {"protected_namespaces": ()}
    prompt: str
    max_tokens: int = 256
    temperature: float = 0.7
    model: Optional[str] = None


class InferenceResponse(BaseModel):
    """Output received from the inference execution."""
    success: bool
    text: str = ""
    tokens_generated: int = 0
    elapsed_sec: float = 0.0
    error: Optional[str] = None
