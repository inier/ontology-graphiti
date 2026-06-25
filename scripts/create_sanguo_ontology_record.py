"""创建三国本体记录"""
import requests

BASE = "http://localhost:8000"

# 登录
r = requests.post(f"{BASE}/api/auth/login", json={"username": "admin", "password": "admin123"}, timeout=10)
TOKEN = r.json()["access_token"]
H = {"Authorization": f"Bearer {TOKEN}"}

# 获取工作空间X的ID
r = requests.get(f"{BASE}/api/workspaces", headers=H, timeout=10)
ws_list = r.json()
ws_x = next((ws for ws in ws_list.get("workspaces", []) if ws["name"] == "X"), None)

if not ws_x:
    print("未找到工作空间 X")
    exit(1)

ws_id = ws_x["workspace_id"]
print(f"工作空间: {ws_id}")

# 获取场景X-1的ID
r = requests.get(f"{BASE}/api/workspaces/{ws_id}/scenarios", headers=H, timeout=10)
scenarios = r.json()
scenario_x1 = next((sc for sc in scenarios.get("scenarios", []) if sc["name"] == "X-1"), None)
scenario_id = scenario_x1["scenario_id"] if scenario_x1 else None
print(f"场景: {scenario_id}")

# 创建本体
print("创建三国本体...")
r = requests.post(f"{BASE}/api/ontologies", headers=H, json={
    "name": "SanguoOntology",
    "description": "三国演义本体 - 包含人物、势力、地点、事件等实体类型",
    "workspace_id": ws_id,
    "scenario_id": scenario_id,
}, timeout=10)

if r.status_code == 200:
    ont = r.json()
    print(f"本体创建成功!")
    print(f"  ID: {ont.get('ontology_id')}")
    print(f"  名称: {ont.get('name')}")
else:
    print(f"创建失败: {r.status_code} - {r.text}")

# 验证本体列表
print()
print("=== 本体列表 ===")
r = requests.get(f"{BASE}/api/ontologies", headers=H, timeout=10)
ont_list = r.json()
for ont in ont_list.get("ontologies", []):
    print(f"{ont.get('ontology_id')}: {ont.get('name')}")