# DistributedMesh AI - RAM Governor & Distributed Inference Orchestrator

A distributed local AI inference orchestrator and real-time RAM governor designed specifically for Windows PCs connected to a Local Area Network (LAN), controlled seamlessly from an external laptop without requiring administrator privileges or port forwarding.

---

## 🌟 Key Architecture & Highlights

```
 ┌───────────────────────────────────────────────────────────────┐
 │               YOUR LAPTOP (Outside the LAN)                  │
 │                                                               │
 │   • Telegram App (Desktop / Web / Mobile)                    │
 │     Commands: /status, /ram, /split, /clean, /ask            │
 │   • Or Laptop CLI: python -m laptop_client.client_cli         │
 └───────────────────────────────┬───────────────────────────────┘
                                 │ Encrypted HTTPS / Outbound Polling
                                 │ (No Admin, No Port Forwarding)
                                 ▼
 ┌───────────────────────────────────────────────────────────────┐
 │                   LAN: MASTER / COORDINATOR PC                │
 │   IP: 192.168.1.100 (Port 8500)                              │
 │   • Heartbeat tracker & node registry                         │
 │   • Dynamic Layer Balancer (calculates splits per free RAM)   │
 │   • Web Dashboard (http://<lan-ip>:8500)                      │
 │   • Telegram Bot daemon                                       │
 └──────────────┬────────────────────────────────┬───────────────┘
                │ LAN Heartbeats & RPC           │ LAN Heartbeats & RPC
                ▼                                ▼
 ┌───────────────────────────────┐ ┌───────────────────────────────┐
 │         LAN: WORKER PC 1      │ │         LAN: WORKER PC 2      │
 │   • Win32 Memory Monitor      │ │   • Win32 Memory Monitor      │
 │   • Active OOM Guard          │ │   • Active OOM Guard          │
 │   • WorkingSet Memory Trim    │ │   • WorkingSet Memory Trim    │
 │   • llama.cpp RPC / Fallback  │ │   • llama.cpp RPC / Fallback  │
 └───────────────────────────────┘ └───────────────────────────────┘
```

1. **Zero Admin Privileges Required**:
   - Everything runs strictly within user-space permissions.
   - Installs dependencies using `pip install --user`.
   - Uses native Windows Win32 APIs (`GlobalMemoryStatusEx` and `EmptyWorkingSet`) via standard Python `ctypes` without triggering UAC prompts.
2. **True Remote Laptop Control**:
   - Because the worker PCs are on a LAN and your laptop is outside that LAN, incoming connections to the LAN would normally require complex router port forwarding or VPNs.
   - **Solution**: The Coordinator connects outward to Telegram's cloud API over port 443. Your laptop talks directly to the Telegram Bot! This passes through any firewall or NAT router seamlessly with 0 configuration.
3. **Dynamic Layer Splitting by RAM**:
   - Proportionally distributes model transformer layers (e.g., 32 layers for 8B models, 80 layers for 70B models) based on each node's real-time free physical RAM and GPU VRAM.
   - Preserves an emergency safety buffer (e.g. 1.2 GB) so Windows never freezes.
4. **OOM Guard & Active Memory Trimming**:
   - Monitors RAM thresholds continuously.
   - If free memory drops below the critical safety margin, it automatically purges working sets and pushes an alert directly to your laptop.

---

## 🚀 Fast Installation (Zero Admin)

Open **Command Prompt (`cmd`)** or **PowerShell** on each computer (no "Run as Administrator" needed):

### Option A: 1-Click Batch File (CMD)
```bat
install.bat
```

### Option B: PowerShell
```powershell
.\install.ps1
```

### Option C: Manual Command
```bash
python -m pip install -r requirements.txt --user
```

---

## ⚙️ Configuration (`config.json`)

Edit `config.json` on your Master PC or laptop:

```json
{
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
    "coordinator_url": "https://ramusage-3656d30fbed9.herokuapp.com",
    "shared_secret": "neuro_mesh_secret_2026",
    "heartbeat_interval_sec": 3
  },
  "ram_guard": {
    "min_free_ram_mb": 800,
    "critical_ram_mb": 400,
    "reserve_buffer_mb": 1200,
    "auto_trim_working_set": true
  },
  "telegram": {
    "enabled": false,
    "bot_token": "YOUR_TELEGRAM_BOT_TOKEN_FROM_BOTFATHER",
    "authorized_chat_ids": []
  }
}
```

---

## 🔒 Security & Public URL Protection

When running your coordinator on Heroku (`https://ramusage-3656d30fbed9.herokuapp.com`), the URL is reachable over the internet. **Is it protected from being hacked? YES:**

1. **End-to-End Cluster Secret Token**:
   - All cluster commands (`/api/models/load`, `/api/infer`, `/api/trim`, `/api/cluster/codered`, `/api/pcs`, `/api/heartbeat`) require the `X-Cluster-Secret` header or authenticated cookie.
   - Any unauthorized visitor or automated internet scanner receives **`401 Unauthorized`** and is completely blocked.
2. **Dashboard Lock Screen**:
   - Visiting `https://ramusage-3656d30fbed9.herokuapp.com` in a browser presents an encrypted Lock Screen. No PC names, IPs, or memory statistics are visible without typing your secret password.
3. **HTTPS / TLS 1.3 Encryption**:
   - Traffic between your laptop, workers, and Heroku is 100% encrypted over HTTPS. Nobody on public Wi-Fi or internet service providers can intercept passwords or telemetry.
4. **Zero Inbound Port Forwarding on Worker PCs**:
   - Worker computers communicate **outward** to Heroku over standard HTTPS. They do NOT expose any open ports to the public internet on your home/office router. They remain shielded behind your local router NAT firewall.
5. **Custom Secret in Heroku**:
   - You can change your secret key anytime in your Heroku Dashboard under **Settings -> Config Vars** by adding `CLUSTER_SECRET = your_custom_password`.

---

## 🖥️ How to Run

### Step 1: Cloud Coordinator (Heroku 24/7)
Your permanent cloud coordinator is live at:
`https://ramusage-3656d30fbed9.herokuapp.com`

*(Or run locally on your LAN with `start_coordinator.bat` / `python -m coordinator.coordinator`)*

### Step 2: Start Workers (on each PC)
On each worker PC, simply use one of the 3 simple batch files:

1. **`run_forever.bat`** (Recommended ⭐): Runs silently in the background, keeps PC awake even when locked (`Win + L`), and automatically restarts on Windows reboot.
2. **`start.bat`**: Starts the worker process in live console mode so you can see live logs.
3. **`stop.bat`**: Cleanly stops the worker process and removes auto-start.

*(Or run remotely via: `irm https://ramusageailaptop.netlify.app/join.ps1 | iex`)*

Each worker immediately registers with the coordinator and begins streaming RAM statistics!

---

## ⚡ Auto-Start & Always-On (Lock-Screen Persistence)

To ensure your PC stays awake, never goes to sleep, and starts automatically on reboot:

### 1. Hardware Power-On (BIOS Setting)
When electricity returns after a power outage:
1. Turn on the PC and press `DEL` or `F2` to enter BIOS.
2. Go to **Power Management** / **Advanced**.
3. Look for **"AC Power Loss"**, **"Restore on AC Power Loss"**, or **"State After G3"**.
4. Change it from *Power Off* to **"Power On"** (or *Last State*).
5. Save & Exit (`F10`). Now, the PC turns on automatically whenever wall power is restored!

### 2. Software 24/7 Setup (Zero Admin)
Double-click **`run_forever.bat`** once:
- **Always On**: Keeps CPU & network alive even when your PC is locked (`Win + L`). Your monitor can safely turn off to save power, but Windows will never enter sleep mode.
- **Autostart**: Places a silent launcher into Windows User Startup (`%APPDATA%\...\Startup`) and `HKCU\Run`.
- **Headless**: Runs invisibly in the background with zero open windows.
- **To Stop**: Just double-click **`stop.bat`**.

---

## 📱 Controlling from Your External Laptop

You have two powerful options to control your cluster from your laptop:

### Option A: Native PowerShell CLI (`mesh.ps1`) ⭐ (No Python Required on Laptop)
You can control the entire cluster, discover local models, and run prompts directly from PowerShell:

```powershell
# 1. View all downloaded models across all PCs (LM Studio, Ollama, GGUF)
.\mesh.ps1 models

# 2. Select and run a model (by number or name)
.\mesh.ps1 load 1
# Output: Automatically splits layers across PC-1 & PC-2 based on free RAM!

# 3. Chat with the running model
.\mesh.ps1 ask "Explain quantum computing in simple terms"

# 4. View connected PCs and live RAM load
.\mesh.ps1 pcs

# 5. Flush and reclaim RAM across all machines
.\mesh.ps1 clean

# 6. Unload model when done
.\mesh.ps1 unload

# 7. 🚨 CODE RED: Completely wipe and uninstall software from all worker PCs
.\mesh.ps1 codered
# Prompts for 'CONFIRM', then wipes all processes, registry keys, and files from all worker PCs!

# Or open the interactive PowerShell menu:
.\mesh.ps1
```

> **Zero Model Uploads**: You never need to upload large multi-gigabyte models across your network or Telegram. The system automatically scans each PC's local **LM Studio** (`~/.lmstudio/models`), **Ollama**, and GGUF folders, reads the model architecture (layers, params, quantization) instantly, and runs it right where it's stored!

---

### Option B: Telegram Bot (From Laptop or Mobile Anywhere)
Open Telegram on your laptop or phone and send:

| Command | Action |
|---|---|
| `/models` | **List all downloaded models** across all PCs (LM Studio, Ollama, etc.) |
| `/load <id>` | **Select & launch model** with automatic RAM layer balancing |
| `/unload` | **Unload model** and release RAM across all PCs |
| `/pcs` | **Show exact count and directory of all connected PCs** (Online vs Offline) |
| `/status` | View cluster overview, connected PC count, and live RAM load |
| `/ram` | Deep breakdown of physical RAM, pagefile, GPU VRAM, and process load |
| `/nodes` | List all LAN IP addresses and RPC ports |
| `/split [layers]` | Dynamic calculation of model layers based on current free RAM |
| `/clean` | Instant working set flush & garbage collection across all nodes |
| `/ask <prompt>` | Run distributed inference and receive the generated output |

---

### Option C: Interactive Python Laptop CLI
If you prefer running Python on your laptop:
```bash
python -m laptop_client.client_cli --url http://192.168.1.100:8500
```
Available CLI commands:
- `models`: Scan & list local models on all machines
- `load <id>`: Balance and load model
- `unload`: Release active model
- `pcs`: Show connected PC directory & count
- `status` / `ram`: Memory & cluster diagnostics
- `clean`: Flush memory
- `ask <prompt>`: Distributed prompt inference

---

## 🧠 Distributed AI Inference Integration (`llama.cpp` RPC)

When you ask the coordinator to split a model (e.g. `/split 32`), the cluster returns:
```text
PC-1 (16GB RAM): 18 layers (L0 to L17)
PC-2 (8GB RAM):  6 layers  (L18 to L23)
PC-3 (GPU):      8 layers  (L24 to L31)

RPC Flag:
--rpc 192.168.1.101:50052,192.168.1.102:50052,192.168.1.103:50052
```

To run `llama.cpp` inference across the whole network:
```bash
llama-cli.exe -m models/Meta-Llama-3-8B-Instruct.Q4_K_M.gguf --rpc 192.168.1.101:50052,192.168.1.102:50052,192.168.1.103:50052 -p "Hello world"
```
The coordinator and workers automatically track and protect memory during generation.

---

## 🧪 Verification & Self-Test

Run the built-in diagnostic test suite to verify Win32 memory calls and zero-admin permissions:
```bash
python test_system.py
```
Run the full integration test:
```bash
python test_integration.py
```
Both tests run 100% offline and require zero configuration.
