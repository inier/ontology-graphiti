"""创建三国战纪智能体（通过平台 API）"""
import requests
import json

BASE = "http://localhost:8000"

# Login
r = requests.post(f"{BASE}/api/auth/login",
                  json={"username": "admin", "password": "admin123"}, timeout=10)
TOKEN = r.json()["access_token"]
H = {"Authorization": f"Bearer {TOKEN}", "Content-Type": "application/json"}

# 1. Get entity type IDs
r = requests.get(f"{BASE}/api/ontology/model/entity-types", headers=H, timeout=10)
data = r.json()
if isinstance(data, dict):
    items = data.get("entity_types", data.get("types", data.get("items", [])))
else:
    items = data
sanguo_types = [t for t in items if t.get("name", "").startswith("Sanguo")]
print("Sanguo types:", [(t["name"], t["type_id"]) for t in sanguo_types])

# 2. Get skills
r = requests.get(f"{BASE}/api/skill/skills", headers=H, params={"page_size": 100}, timeout=10)
skills = r.json()
if isinstance(skills, dict):
    skills = skills.get("skills", skills.get("items", []))
skill_ids = [s.get("skill_id") or s.get("id") for s in skills if s.get("skill_id") or s.get("id")]
print(f"Available skills: {len(skill_ids)}")

# 3. Get workspace
r = requests.get(f"{BASE}/api/workspaces", headers=H, timeout=10)
ws_data = r.json()
if isinstance(ws_data, dict):
    ws_list = ws_data.get("workspaces", ws_data.get("items", []))
else:
    ws_list = ws_data
ws = next((w for w in ws_list if w.get("name") == "X"), None)
ws_id = ws.get("workspace_id", ws.get("id")) if ws else ""
print(f"Workspace X: {ws_id}")

# 4. Check if agent already exists
r = requests.get(f"{BASE}/api/agent-management", headers=H, timeout=10)
existing = r.json()
if isinstance(existing, dict):
    existing = existing.get("agents", existing.get("items", []))
sanguo_agent = next((a for a in existing if a.get("name") == "sanguo_warrior"), None)

if sanguo_agent:
    print(f"Agent already exists: {sanguo_agent.get('agent_id')}")
    agent_id = sanguo_agent.get("agent_id")
else:
    # 5. Create agent
    agent_data = {
        "name": "sanguo_warrior",
        "display_name": "三国战纪",
        "avatar": "",
        "description": "三国演义知识智能体，基于本体数据回答三国历史、人物、战役、势力等问题，支持动态推演",
        "main_object": sanguo_types[0]["type_id"] if sanguo_types else "",
        "related_objects": [t["type_id"] for t in sanguo_types[1:]] if len(sanguo_types) > 1 else [],
        "related_skills": skill_ids[:5],
        "workspace_id": ws_id,
    }
    r = requests.post(f"{BASE}/api/agent-management", headers=H, json=agent_data, timeout=10)
    print(f"Create agent: {r.status_code}")
    if r.status_code == 200:
        agent = r.json()
        agent_id = agent.get("agent_id")
        print(f"  agent_id: {agent_id}")
        print(f"  display_name: {agent.get('display_name')}")
    else:
        print(f"  error: {r.text[:300]}")
        agent_id = None

# 6. Test QA with the agent
if agent_id:
    print()
    print("=== Testing QA ===")
    questions = [
        "三国演义中有哪些主要人物？",
        "赤壁之战发生在哪一年？",
        "刘备和关羽是什么关系？",
    ]
    for q in questions:
        r = requests.post(f"{BASE}/api/qa/ask", headers=H, json={
            "question": q,
            "workspace_id": ws_id,
            "agent_id": agent_id,
        }, timeout=30)
        if r.status_code == 200:
            ans = r.json()
            answer_text = ans.get("answer", ans.get("response", ""))
            print(f"Q: {q}")
            print(f"A: {answer_text[:200]}...")
            print()
        else:
            print(f"Q: {q} -> ERROR {r.status_code}: {r.text[:200]}")
            print()
