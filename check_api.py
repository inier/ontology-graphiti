import requests
import json

base_url = "http://localhost:8000"

print("=== 测试后端 API ===\n")

# 1. 测试 workspace 列表
try:
    resp = requests.get(f"{base_url}/api/workspaces?page_size=100", timeout=5)
    print(f"GET /api/workspaces -> {resp.status_code}")
    if resp.status_code == 200:
        data = resp.json()
        ws_list = data.get("workspaces", [])
        print(f"  工作空间数: {len(ws_list)}")
        for ws in ws_list[:3]:
            print(f"  - {ws.get('workspace_id', '?')[:8]}... name={ws.get('name')}")
    else:
        print(f"  Error: {resp.text[:200]}")
except Exception as e:
    print(f"  连接失败: {e}")

# 2. 测试场景列表
try:
    resp = requests.get(f"{base_url}/api/workspaces", timeout=5)
    if resp.status_code == 200:
        data = resp.json()
        ws_list = data.get("workspaces", [])
        if ws_list:
            ws_id = ws_list[0].get("workspace_id")
            resp2 = requests.get(f"{base_url}/api/workspaces/{ws_id}/scenarios", timeout=5)
            print(f"\nGET /api/workspaces/{ws_id[:8]}.../scenarios -> {resp2.status_code}")
            if resp2.status_code == 200:
                sc_data = resp2.json()
                print(f"  场景数: {sc_data.get('total', 0)}")
except Exception as e:
    print(f"  场景查询失败: {e}")

# 3. 测试语义地图 API
try:
    resp = requests.get(f"{base_url}/api/semantic-map", timeout=5)
    print(f"\nGET /api/semantic-map -> {resp.status_code}")
    if resp.status_code == 200:
        data = resp.json()
        print(f"  语义地图数: {data.get('total', 0)}")
except Exception as e:
    print(f"  语义地图查询失败: {e}")

# 4. 测试 QA API
try:
    resp = requests.post(f"{base_url}/api/qa/ask", json={"question": "测试"}, timeout=10)
    print(f"\nPOST /api/qa/ask -> {resp.status_code}")
    if resp.status_code == 200:
        data = resp.json()
        print(f"  回答: {data.get('answer', '')[:100]}...")
except Exception as e:
    print(f"  QA查询失败: {e}")

# 5. 测试本地开发入口
print("\n\n=== 测试本地开发入口 (8765) ===\n")
try:
    resp = requests.get("http://localhost:8765/api/workspaces?page_size=100", timeout=5)
    print(f"GET :8765/api/workspaces -> {resp.status_code}")
    if resp.status_code == 200:
        data = resp.json()
        print(f"  工作空间数: {len(data.get('workspaces', []))}")
except Exception as e:
    print(f"  本地开发入口连接失败: {e}")
