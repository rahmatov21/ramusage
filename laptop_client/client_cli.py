"""Interactive CLI for the remote laptop to monitor and control the LAN cluster.
Works with any URL (Cloudflare Tunnel, ngrok, reverse proxy, or VPN).
"""

import argparse
import sys
import time
import requests

from common.utils import format_bar, format_mb


class MeshLaptopClient:
    def __init__(self, coordinator_url: str):
        self.url = coordinator_url.rstrip("/")

    def get_pcs(self):
        """Fetch and display exact PC count and status directory."""
        try:
            r = requests.get(f"{self.url}/api/status", timeout=5)
            if r.status_code != 200:
                print(f"[ERROR] Failed to fetch PC count: {r.status_code}")
                return
            data = r.json()
            nodes = data.get("nodes", {})
            total = data.get("total_nodes", len(nodes))
            online = data.get("online_nodes", 0)
            offline = max(0, total - online)

            print("\n" + "=" * 65)
            print("  🖥️  Cluster PC Count & Status Directory")
            print("=" * 65)
            print(f"  Total Registered PCs: {total}")
            print(f"  • Online PCs:         {online}")
            print(f"  • Offline PCs:        {offline}")
            print("-" * 65)
            if not nodes:
                print("  No PCs registered yet. Start workers on your LAN machines.")
            else:
                for idx, (nid, n) in enumerate(nodes.items(), 1):
                    mem = n.get("memory", {})
                    avail_mb = mem.get("avail_ram_mb", 0.0)
                    tot_mb = mem.get("total_ram_mb", 0.0)
                    state_sym = "[ONLINE]" if n.get("status") == "online" else "[OFFLINE]"
                    rpc_sym = "RPC: ON" if n.get("rpc_running") else "RPC: OFF"
                    print(f"  {idx}. {nid:<15} {state_sym:<10} IP: {n.get('ip_address'):<15} RAM: {format_mb(avail_mb)}/{format_mb(tot_mb)} | {rpc_sym}")
            print("=" * 65 + "\n")
        except Exception as e:
            print(f"[ERROR] Connection failed: {e}")

    def get_status(self):
        try:
            r = requests.get(f"{self.url}/api/status", timeout=5)
            if r.status_code != 200:
                print(f"[ERROR] Failed to fetch status: {r.status_code}")
                return
            data = r.json()
            tot = data.get("total_cluster_ram_gb", 0.0)
            free = data.get("free_cluster_ram_gb", 0.0)
            used = max(0.0, tot - free)
            pct = (used / tot * 100) if tot > 0 else 0
            bar = format_bar(pct, 12)

            print("\n" + "=" * 65)
            print(f"  Cluster: {data.get('cluster_name')}")
            print(f"  🖥️  Connected PCs: {data.get('online_nodes')} Online ({data.get('total_nodes')} Total Registered)")
            print(f"  RAM Usage: {used:.1f} GB / {tot:.1f} GB ({pct:.0f}%) [{bar}]")
            print(f"  Available Free RAM: {free:.2f} GB")
            print("=" * 65)

            nodes = data.get("nodes", {})
            if not nodes:
                print("  No PCs currently registered.")
            for nid, n in nodes.items():
                m = n.get("memory", {})
                avail_mb = m.get("avail_ram_mb", 0.0)
                tot_mb = m.get("total_ram_mb", 0.0)
                vram_free = m.get("vram_free_mb")
                vram_str = f" | VRAM: {vram_free:.0f}MB" if vram_free else ""
                rpc_state = "RPC: ON" if n.get("rpc_running") else "RPC: OFF"
                print(f"  • {nid:<15} [{n.get('status'):<8}] Free: {format_mb(avail_mb):<9} ({m.get('percent_used', 0):.0f}% used) | CPU: {n.get('cpu_percent', 0):.0f}% | {rpc_state}{vram_str}")
            print("=" * 65 + "\n")
        except Exception as e:
            print(f"[ERROR] Connection failed: {e}")

    def get_ram(self):
        try:
            r = requests.get(f"{self.url}/api/status", timeout=5)
            if r.status_code != 200:
                print(f"[ERROR] Failed to fetch RAM stats: {r.status_code}")
                return
            nodes = r.json().get("nodes", {})
            print("\n" + "=" * 65)
            print("  Detailed Memory Breakdown per Worker PC")
            print("=" * 65)
            for nid, n in nodes.items():
                m = n.get("memory", {})
                print(f"  PC: {nid} ({n.get('ip_address')})")
                print(f"    Total Physical RAM: {format_mb(m.get('total_ram_mb', 0))}")
                print(f"    Available RAM:      {format_mb(m.get('avail_ram_mb', 0))}")
                print(f"    Memory Load:        {m.get('percent_used', 0):.1f}%")
                print(f"    Swap / Pagefile:    {format_mb(m.get('swap_avail_mb', 0))} free / {format_mb(m.get('swap_total_mb', 0))}")
                print(f"    Process Memory:     {format_mb(m.get('process_ram_mb', 0))}")
                if m.get("vram_total_mb"):
                    print(f"    GPU VRAM:           {format_mb(m.get('vram_free_mb', 0))} free / {format_mb(m.get('vram_total_mb', 0))}")
                if m.get("is_oom_critical"):
                    print("    ⚠️  CRITICAL: Node is at risk of Out-Of-Memory!")
                print()
            print("=" * 65 + "\n")
        except Exception as e:
            print(f"[ERROR] Connection failed: {e}")

    def get_models(self):
        try:
            r = requests.get(f"{self.url}/api/models", timeout=8)
            if r.status_code != 200:
                print(f"[ERROR] Failed to fetch models: {r.status_code}")
                return []
            models = r.json()
            print("\n" + "=" * 70)
            print("  📦  Local AI Models Available Across Cluster (LM Studio & Local)")
            print("=" * 70)
            if not models:
                print("  No models found. Place .gguf files in LM Studio or models/ folder.")
            else:
                for idx, m in enumerate(models, 1):
                    print(f"  [{idx}] {m.get('name')}")
                    print(f"      Size: {m.get('size_gb')} GB ({m.get('size_mb')} MB) | Arch: {m.get('architecture')} | Layers: {m.get('layers')} | Source: {m.get('source')}")
                    print(f"      Found on: {m.get('node_id') or 'LAN'}")
            print("=" * 70)
            print("  To load and run on cluster: load <number_or_name> (e.g. load 1)")
            print("=" * 70 + "\n")
            return models
        except Exception as e:
            print(f"[ERROR] Connection failed: {e}")
            return []

    def load_model(self, identifier: str):
        try:
            r = requests.get(f"{self.url}/api/models", timeout=8)
            models = r.json() if r.status_code == 200 else []
            target = None

            if identifier.isdigit():
                idx = int(identifier) - 1
                if 0 <= idx < len(models):
                    target = models[idx]
            else:
                for m in models:
                    if identifier.lower() in m.get("name", "").lower():
                        target = m
                        break

            if target:
                req_data = {
                    "model_name": target.get("name"),
                    "layers": target.get("layers", 32),
                    "size_mb": target.get("size_mb", 4800.0),
                }
            else:
                req_data = {
                    "model_name": identifier,
                    "layers": 32,
                    "size_mb": 4800.0,
                }

            print(f"[INFO] Configuring cluster and loading model '{req_data['model_name']}'...")
            resp = requests.post(f"{self.url}/api/models/load", json=req_data, timeout=15)
            if resp.status_code == 200:
                data = resp.json()
                plan = data.get("plan", {})
                print("\n" + "=" * 65)
                print(f"  [SUCCESS] Model '{req_data['model_name']}' Loaded & Running on Cluster!")
                print("=" * 65)
                for a in plan.get("allocations", []):
                    print(f"  • {a.get('node_id')}: {a.get('layers')} layers (L{a.get('start_layer')}-L{a.get('end_layer')}) | RAM Assigned: ~{format_mb(a.get('assigned_ram_mb', 0))}")
                endpoints = plan.get("rpc_endpoints", [])
                if endpoints:
                    print(f"\n  Active RPC Endpoints: {','.join(endpoints)}")
                print("=" * 65)
                print("  You can now ask questions using: ask \"<your prompt>\"\n")
            else:
                print(f"[ERROR] Failed to load model: {resp.status_code} - {resp.text}")
        except Exception as e:
            print(f"[ERROR] Load request failed: {e}")

    def unload_model(self):
        try:
            print("[INFO] Unloading active model and freeing cluster RAM...")
            r = requests.post(f"{self.url}/api/models/unload", timeout=10)
            if r.status_code == 200:
                print("[SUCCESS] Model unloaded. All worker RAM released.\n")
            else:
                print(f"[ERROR] Failed: {r.status_code}")
        except Exception as e:
            print(f"[ERROR] Request failed: {e}")

    def calculate_split(self, layers: int = 32):
        try:
            r = requests.post(
                f"{self.url}/api/split",
                json={"total_layers": layers, "model_name": "Llama-3-8B-Q4"},
                timeout=5,
            )
            if r.status_code != 200:
                print(f"[ERROR] Failed to calculate split: {r.status_code}")
                return
            data = r.json()
            print("\n" + "=" * 60)
            print(f"  Dynamic Model Layer Split ({layers} Layers)")
            print("=" * 60)
            allocs = data.get("allocations", [])
            for a in allocs:
                print(f"  • {a.get('node_id'):<14}: {a.get('layers'):>2} layers (L{a.get('start_layer')}-L{a.get('end_layer')}) | Headroom: {format_mb(a.get('usable_ram_mb', 0)):<9} | Assigned: ~{format_mb(a.get('assigned_ram_mb', 0))}")
            endpoints = data.get("rpc_endpoints", [])
            if endpoints:
                print(f"\n  llama.cpp RPC command flag:\n  --rpc {','.join(endpoints)}")
            for w in data.get("warnings", []):
                print(f"  ⚠️  Warning: {w}")
            print("=" * 60 + "\n")
        except Exception as e:
            print(f"[ERROR] Connection failed: {e}")

    def trim_ram(self):
        try:
            print("[INFO] Requesting RAM trim and working set flush across cluster...")
            r = requests.post(f"{self.url}/api/trim", timeout=10)
            if r.status_code == 200:
                results = r.json().get("results", {})
                total_freed = sum(res.get("freed_ram_mb", 0.0) for res in results.values())
                print(f"[SUCCESS] Trim complete! Recovered {format_mb(total_freed)} RAM across cluster.")
                for nid, res in results.items():
                    print(f"  • {nid}: Freed {res.get('freed_ram_mb', 0.0):.1f} MB (Now {format_mb(res.get('available_ram_mb', 0.0))} available)")
            else:
                print(f"[ERROR] Trim request failed: {r.status_code}")
        except Exception as e:
            print(f"[ERROR] Request failed: {e}")

    def start_workers(self):
        try:
            print("[INFO] Commanding all worker nodes to start RPC backends...")
            r = requests.post(f"{self.url}/api/workers/start", timeout=10)
            if r.status_code == 200:
                print("[SUCCESS] RPC start command issued to all nodes.")
            else:
                print(f"[ERROR] Failed: {r.status_code}")
        except Exception as e:
            print(f"[ERROR] Request failed: {e}")

    def stop_workers(self):
        try:
            print("[INFO] Commanding all worker nodes to stop RPC backends...")
            r = requests.post(f"{self.url}/api/workers/stop", timeout=10)
            if r.status_code == 200:
                print("[SUCCESS] RPC stop command issued to all nodes.")
            else:
                print(f"[ERROR] Failed: {r.status_code}")
        except Exception as e:
            print(f"[ERROR] Request failed: {e}")

    def ask(self, prompt: str):
        try:
            print(f"[INFO] Dispatching prompt to cluster...")
            t0 = time.time()
            r = requests.post(f"{self.url}/api/infer", json={"prompt": prompt}, timeout=60)
            if r.status_code == 200:
                res = r.json()
                if res.get("success"):
                    print("\n" + "=" * 50)
                    print(res.get("text"))
                    print("=" * 50)
                    print(f"Tokens: {res.get('tokens_generated')} | Time: {res.get('elapsed_sec')}s\n")
                else:
                    print(f"[ERROR] Inference error: {res.get('error')}")
            else:
                print(f"[ERROR] HTTP {r.status_code}: {r.text}")
        except Exception as e:
            print(f"[ERROR] Inference request failed: {e}")


def interactive_loop(client: MeshLaptopClient):
    print("\n" + "#" * 60)
    print("  DistributedMesh AI - Remote Laptop Control CLI")
    print(f"  Target URL: {client.url}")
    print("  Type 'help' for command list, 'exit' to quit.")
    print("#" * 60 + "\n")

    while True:
        try:
            cmd = input("mesh> ").strip()
            if not cmd:
                continue
            parts = cmd.split(maxsplit=1)
            action = parts[0].lower()
            arg = parts[1] if len(parts) > 1 else ""

            if action in ("exit", "quit", "q"):
                print("Exiting.")
                break
            elif action in ("models", "list", "model", "m"):
                client.get_models()
            elif action in ("load", "run", "l"):
                if not arg:
                    print("Usage: load <model_number_or_name> (e.g. load 1)")
                else:
                    client.load_model(arg)
            elif action in ("unload", "stop_model"):
                client.unload_model()
            elif action in ("pcs", "count", "computers", "p"):
                client.get_pcs()
            elif action in ("status", "s"):
                client.get_status()
            elif action in ("ram", "mem"):
                client.get_ram()
            elif action in ("split", "layers"):
                layers = int(arg) if arg.isdigit() else 32
                client.calculate_split(layers)
            elif action in ("trim", "clean"):
                client.trim_ram()
            elif action in ("start", "start_workers"):
                client.start_workers()
            elif action in ("stop", "stop_workers"):
                client.stop_workers()
            elif action in ("ask", "infer"):
                if not arg:
                    print("Usage: ask <your prompt here>")
                else:
                    client.ask(arg)
            elif action in ("help", "?"):
                print("\nCommands:")
                print("  models / list   - Scan & show all local downloaded models (LM Studio & files)")
                print("  load <number>   - Auto-calculate RAM split & deploy model across cluster")
                print("  unload          - Unload active model & free all worker RAM")
                print("  pcs / count     - Show exact count and status of all connected PCs")
                print("  status          - View PC count, RAM load, and active overview")
                print("  ram             - Detailed memory breakdown per machine")
                print("  ask <prompt>    - Send prompt to cluster and stream answer")
                print("  clean / trim    - Recover unused memory across all PCs")
                print("  exit            - Quit CLI\n")
            else:
                print(f"Unknown command: '{action}'. Type 'help' for options.")
        except KeyboardInterrupt:
            print("\nExiting.")
            break


def main():
    parser = argparse.ArgumentParser(description="Laptop Controller for Distributed Mesh")
    parser.add_argument(
        "--url",
        type=str,
        default="http://127.0.0.1:8500",
        help="Coordinator URL (e.g. https://xxxx.trycloudflare.com or http://192.168.1.100:8500)",
    )
    args = parser.parse_args()
    client = MeshLaptopClient(args.url)
    interactive_loop(client)


if __name__ == "__main__":
    main()
