"""重新创建三国本体"""
import requests

BASE = "http://localhost:8000"

r = requests.post(f"{BASE}/api/auth/login", json={"username": "admin", "password": "admin123"}, timeout=10)
TOKEN = r.json()["access_token"]
H = {"Authorization": f"Bearer {TOKEN}"}

# 找到工作空间X
r = requests.get(f"{BASE}/api/workspaces", headers=H, timeout=10)
ws_list = r.json()
ws_x = next((ws for ws in ws_list.get("workspaces", []) if ws["name"] == "X"), None)

if not ws_x:
    print("未找到工作空间 X，创建新工作空间")
    r = requests.post(f"{BASE}/api/workspaces", headers=H, json={
        "name": "X",
        "description": "三国演义本体测试工作空间",
        "isolation_level": "STANDARD"
    }, timeout=10)
    ws_x = r.json()

ws_id = ws_x["workspace_id"]
print(f"工作空间: {ws_id} - {ws_x['name']}")

# 创建本体
print("创建三国本体...")
r = requests.post(f"{BASE}/api/ontology-management/ontologies", headers=H, json={
    "name": "SanguoOntology",
    "description": "三国演义本体",
    "workspace_id": ws_id,
    "status": "active"
}, timeout=10)

if r.status_code == 200:
    ont = r.json()
    print(f"本体创建成功: {ont['ontology_id']}")
else:
    print(f"创建失败: {r.text}")