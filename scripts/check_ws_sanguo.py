"""检查工作空间 22c6a2e2-dbd4-44b5-9a93-7a25a03598be"""
import requests

BASE = "http://localhost:8000"

r = requests.post(f"{BASE}/api/auth/login", json={"username": "admin", "password": "admin123"}, timeout=10)
TOKEN = r.json()["access_token"]
H = {"Authorization": f"Bearer {TOKEN}"}

ws_id = "22c6a2e2-dbd4-44b5-9a93-7a25a03598be"

print("=== 工作空间详情 ===")
r = requests.get(f"{BASE}/api/workspaces/{ws_id}", headers=H, timeout=10)
data = r.json()
print(f"ID: {data.get('workspace_id')}")
print(f"名称: {data.get('name')}")
print(f"描述: {data.get('description')}")
print(f"状态: {data.get('status')}")
print(f"创建时间: {data.get('created_at')}")

print()
print("=== 关联场景 ===")
r = requests.get(f"{BASE}/api/workspaces/{ws_id}/scenarios", headers=H, timeout=10)
scenarios = r.json()
for s in scenarios.get("scenarios", []):
    print(f"- {s.get('scenario_id')}: {s.get('name')}")

print()
print("=== 三国实体类型 ===")
r = requests.get(f"{BASE}/api/ontology/model/entity-types", headers=H, timeout=10)
types = r.json()
sanguo_types = [t for t in (types.get("entity_types", types)) if "Sanguo" in t.get("name", "")]
for t in sanguo_types:
    print(f"{t.get('name')}: {t.get('type_id')}")

print()
print("=== 人物实例数量 ===")
char_type = next((t for t in sanguo_types if t["name"] == "SanguoCharacter"), None)
if char_type:
    r = requests.get(f"{BASE}/api/ontology/model/instances", headers=H, params={"type_id": char_type["type_id"]}, timeout=10)
    instances = r.json()
    total = instances.get("total", len(instances.get("instances", instances)))
    print(f"人物总数: {total}")