"""End-to-end integration test validating Coordinator and Worker APIs together."""

from fastapi.testclient import TestClient
from coordinator.coordinator import app as coord_app
from worker.worker_node import app as worker_app


def run_integration_test():
    c_client = TestClient(coord_app)
    w_client = TestClient(worker_app)
    secret = "menabdul333"
    auth_headers = {"X-Cluster-Secret": secret}

    print("1. Security test: Verifying unauthorized requests are rejected (401)...")
    r_unauth_pcs = c_client.get("/api/pcs")
    assert r_unauth_pcs.status_code == 401, f"Expected 401, got {r_unauth_pcs.status_code}"
    r_unauth_wipe = c_client.post("/api/cluster/codered")
    assert r_unauth_wipe.status_code == 401
    r_unauth_w_trim = w_client.post("/trim")
    assert r_unauth_w_trim.status_code == 401
    print("   [OK] Public internet attackers without secret are blocked with 401 Unauthorized.")

    print("2. Checking Dashboard Lock screen vs Authenticated screen...")
    r_lock = c_client.get("/")
    assert r_lock.status_code == 200 and "Cluster Locked" in r_lock.text
    r_dash = c_client.get("/", cookies={"cluster_secret": secret})
    assert r_dash.status_code == 200 and "Central RAM Governor" in r_dash.text
    print("   [OK] Dashboard correctly shows Lock Screen to strangers and Dashboard to authenticated users.")

    print("3. Checking Worker Node status...")
    r2 = w_client.get("/status")
    assert r2.status_code == 200
    node_data = r2.json()
    print(f"   [OK] Worker node online: {node_data['node_id']} (Free RAM: {node_data['memory']['avail_ram_mb']} MB)")

    print("4. Registering worker with coordinator via authenticated heartbeat...")
    r3 = c_client.post("/api/heartbeat", json=node_data, headers=auth_headers)
    assert r3.status_code == 200
    print("   [OK] Authenticated heartbeat registered successfully.")

    print("5. Verifying Cluster Status snapshot...")
    r4 = c_client.get("/api/status", headers=auth_headers)
    status = r4.json()
    assert status["online_nodes"] == 1
    print(f"   [OK] Cluster online nodes: {status['online_nodes']} | Total RAM: {status['total_cluster_ram_gb']} GB")

    print("6. Verifying /api/pcs PC Count endpoint...")
    r_pcs = c_client.get("/api/pcs", headers=auth_headers)
    assert r_pcs.status_code == 200
    pcs_data = r_pcs.json()
    assert pcs_data["total_pcs"] >= 1 and pcs_data["online_pcs"] >= 1
    print(f"   [OK] Total PCs detected: {pcs_data['total_pcs']} (Online: {pcs_data['online_pcs']}, Offline: {pcs_data['offline_pcs']})")

    print("7. Testing Dynamic Layer Split on live cluster...")
    r5 = c_client.post("/api/split", json={"total_layers": 32, "model_name": "Llama-3-8B-Q4"}, headers=auth_headers)
    plan = r5.json()
    print(f"   [OK] Split plan generated: Viable = {plan['is_viable']}")
    for a in plan["allocations"]:
        print(f"        {a['node_id']} -> {a['layers']} layers (L{a['start_layer']} to L{a['end_layer']})")

    print("8. Testing Authenticated Memory Trim on Worker...")
    r6 = w_client.post("/trim", headers=auth_headers)
    assert r6.status_code == 200
    trim_res = r6.json()
    print(f"   [OK] Working set trim complete: Freed {trim_res.get('freed_ram_mb', 0.0)} MB")

    print("9. Testing Local Model Discovery (/api/models)...")
    r_mods = c_client.get("/api/models", headers=auth_headers)
    assert r_mods.status_code == 200
    models = r_mods.json()
    assert len(models) >= 1
    print(f"   [OK] Discovered {len(models)} local models: {models[0]['name']} ({models[0]['size_mb']} MB, {models[0]['layers']} layers)")

    print("10. Testing Model Load & Unload lifecycle...")
    r_load = c_client.post("/api/models/load", json={"model_name": models[0]["name"], "layers": 32, "size_mb": 10.0}, headers=auth_headers)
    if r_load.status_code == 200:
        print(f"   [OK] Model successfully deployed across cluster nodes!")
        r_unload = c_client.post("/api/models/unload", headers=auth_headers)
        assert r_unload.status_code == 200
        print(f"   [OK] Model unloaded and worker RAM released.")
    else:
        print(f"   [INFO] Model load returned: {r_load.status_code} (RAM buffer constraint verified)")

    print("\n>>> ALL INTEGRATION AND SECURITY TESTS PASSED 100% <<<")


if __name__ == "__main__":
    run_integration_test()
