"""检查本体状态"""
import requests

BASE = "http://localhost:8000"

r = requests.post(f"{BASE}/api/auth/login", json={"username": "admin", "password": "admin123"}, timeout=10)
TOKEN = r.json()["access_token"]
H = {"Authorization": f"Bearer {TOKEN}"}

print("=== 工作空间列表 ===")
r = requests.get(f"{BASE}/api/workspaces", headers=H, timeout=10)
ws_list = r.json()
for ws in ws_list.get("workspaces", []):
    print(f"{ws['workspace_id']}: {ws['name']}")

print()
print("=== 本体列表 ===")
r = requests.get(f"{BASE}/api/ontology-management/ontologies", headers=H, timeout=10)
ont_list = r.json()
for ont in ont_list.get("ontologies", []):
    ws_id = ont.get("workspace_id", "N/A")
    print(f"{ont['ontology_id']}: {ont['name']}")

print()
print("=== 实体类型 ===")
r = requests.get(f"{BASE}/api/ontology/model/entity-types", headers=H, timeout=10)
types = r.json()
sanguo_types = [t for t in (types.get("entity_types", types)) if "Sanguo" in t.get("name", "")]
xiyou_types = [t for t in (types.get("entity_types", types)) if "Xiyou" in t.get("name", "")]
print(f"三国类型数量: {len(sanguo_types)}")
print(f"西游类型数量: {len(xiyou_types)}")

print()
print("=== 三国类型详情 ===")
for t in sanguo_types:
    print(f"  {t.get('name')}")

print()
print("=== 西游类型详情 ===")
for t in xiyou_types:
    print(f"  {t.get('name')}")