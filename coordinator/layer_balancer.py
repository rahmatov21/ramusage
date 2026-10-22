"""Dynamic layer splitting algorithm based on real-time node RAM & VRAM availability."""

from typing import Dict, List, Optional
from common.models import ClusterSplitPlan, LayerAllocation, NodeInfo


class LayerBalancer:
    """Calculates optimal model layer distribution across LAN nodes based on live memory."""

    @staticmethod
    def calculate_split(
        nodes: Dict[str, NodeInfo],
        total_layers: int = 32,
        model_name: str = "Llama-3-8B-Q4",
        model_size_mb: float = 4800.0,
        reserve_buffer_mb: float = 1200.0,
    ) -> ClusterSplitPlan:
        """Dynamically compute layer allocations proportional to available memory."""
        # 1. Filter out offline or unresponsive nodes
        active_nodes = [
            n for n in nodes.values()
            if n.status != "offline" and not n.memory.is_oom_critical
        ]

        if not active_nodes:
            return ClusterSplitPlan(
                model_name=model_name,
                total_layers=total_layers,
                total_available_ram_mb=0.0,
                is_viable=False,
                warnings=["No active online nodes available in cluster."],
            )

        # 2. Calculate usable memory per node (RAM above buffer + free VRAM)
        node_capacities: List[tuple[NodeInfo, float]] = []
        total_usable_mem = 0.0

        for node in active_nodes:
            ram_headroom = max(0.0, node.memory.avail_ram_mb - reserve_buffer_mb)
            vram_headroom = max(0.0, node.memory.vram_free_mb or 0.0)
            # VRAM is weighted equally or slightly higher for layer allocation
            node_usable = ram_headroom + vram_headroom
            node_capacities.append((node, node_usable))
            total_usable_mem += node_usable

        warnings: List[str] = []

        if total_usable_mem <= 0:
            return ClusterSplitPlan(
                model_name=model_name,
                total_layers=total_layers,
                total_available_ram_mb=0.0,
                is_viable=False,
                warnings=[
                    f"All active nodes have less than {reserve_buffer_mb:.0f} MB free RAM buffer."
                ],
            )

        if total_usable_mem < model_size_mb:
            warnings.append(
                f"Cluster usable memory ({total_usable_mem / 1024:.2f} GB) is less than model size ({model_size_mb / 1024:.2f} GB). Paging may occur."
            )

        # 3. Proportional integer layer distribution
        raw_allocations = []
        assigned_layers = []
        remainders = []

        for node, cap in node_capacities:
            if total_usable_mem > 0:
                raw = (cap / total_usable_mem) * total_layers
            else:
                raw = 0.0
            raw_allocations.append(raw)
            base = int(raw)
            assigned_layers.append(base)
            remainders.append((raw - base, len(remainders)))

        # Distribute leftover layers to highest fractional remainders
        leftover = total_layers - sum(assigned_layers)
        remainders.sort(key=lambda x: x[0], reverse=True)
        for i in range(leftover):
            idx = remainders[i][1]
            assigned_layers[idx] += 1

        # 4. Build sequential layer allocations
        allocations: List[LayerAllocation] = []
        rpc_endpoints: List[str] = []
        current_layer_idx = 0
        mb_per_layer = model_size_mb / max(1, total_layers)

        for i, (node, cap) in enumerate(node_capacities):
            num_layers = assigned_layers[i]
            if num_layers > 0:
                start = current_layer_idx
                end = current_layer_idx + num_layers - 1
                current_layer_idx += num_layers

                assigned_ram = num_layers * mb_per_layer
                alloc = LayerAllocation(
                    node_id=node.node_id,
                    ip_address=node.ip_address,
                    rpc_port=node.rpc_port,
                    layers=num_layers,
                    start_layer=start,
                    end_layer=end,
                    usable_ram_mb=round(cap, 1),
                    assigned_ram_mb=round(assigned_ram, 1),
                )
                allocations.append(alloc)
                rpc_endpoints.append(f"{node.ip_address}:{node.rpc_port}")

        return ClusterSplitPlan(
            model_name=model_name,
            total_layers=total_layers,
            total_available_ram_mb=round(total_usable_mem, 1),
            allocations=allocations,
            rpc_endpoints=rpc_endpoints,
            is_viable=True,
            warnings=warnings,
        )
