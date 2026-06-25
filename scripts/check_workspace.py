"""检查工作空间状态"""
import requests

BASE = "http://localhost:8000"

# 登录
r = requests.post(f"{BASE}/api/auth/login", json={"username": "admin", "password": "admin123"}, timeout=10)
TOKEN = r.json()["access_token"]
H = {"Authorization": f"Bearer {TOKEN}", "Content-Type": "application/json"}

# 获取工作空间详情
print("=== 工作空间详情 ===")
r = requests.get(f"{BASE}/api/workspace/workspaces/9faf2fa2-6109-4ab5-bd31-a113555649aa", headers=H, timeout=10)
data = r.json()
print(f"ID: {data.get('workspace_id')}")
print(f"名称: {data.get('name')}")
print(f"描述: {data.get('description')}")
print(f"状态: {data.get('status')}")
print(f"创建时间: {data.get('created_at')}")

# 获取关联场景
print()
print("=== 关联场景 ===")
r = requests.get(f"{BASE}/api/workspace/workspaces/9faf2fa2-6109-4ab5-bd31-a113555649aa/scenarios", headers=H, timeout=10)
scenarios = r.json()
for s in scenarios.get("scenarios", scenarios):
    print(f"- {s.get('scenario_id')}: {s.get('name')} ({s.get('status')})")

# 获取关联本体
print()
print("=== 关联本体 ===")
r = requests.get(f"{BASE}/api/ontology-management/ontologies", headers=H, params={"workspace_id": "9faf2fa2-6109-4ab5-bd31-a113555649aa"}, timeout=10)
ontologies = r.json()
for o in ontologies.get("ontologies", ontologies):
    print(f"- {o.get('ontology_id')}: {o.get('name')} ({o.get('status')})")

# 获取实体类型
print()
print("=== 实体类型 ===")
r = requests.get(f"{BASE}/api/ontology/model/entity-types", headers=H, timeout=10)
types = r.json()
sanguo_types = [t for t in (types.get("entity_types", types)) if "Sanguo" in t.get("name", "")]
print(f"三国相关实体类型: {len(sanguo_types)}")
for t in sanguo_types:
    print(f"  {t.get('name')}: {t.get('type_id')}")

# 获取人物实例数量
print()
print("=== 人物实例 ===")
char_type = next((t for t in sanguo_types if t["name"] == "SanguoCharacter"), None)
if char_type:
    r = requests.get(f"{BASE}/api/ontology/model/instances", headers=H, params={"type_id": char_type["type_id"], "page_size": 5}, timeout=10)
    instances = r.json()
    total = instances.get("total", len(instances.get("instances", instances)))
    print(f"人物总数: {total}")
    insts = instances.get("instances", instances)
    for i in insts[:5]:
        props = i.get("properties", {})
        if isinstance(props, str):
            import json
            props = json.loads(props)
        print(f"  - {props.get('name', '?')} ({props.get('faction', '?')})")