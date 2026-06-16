"""端到端验证脚本：三国智能体全链路测试"""
import requests
import json
import sys

BASE = "http://localhost:8000"

# Login
r = requests.post(f"{BASE}/api/auth/login", json={"username": "admin", "password": "admin123"}, timeout=10)
TOKEN = r.json()["access_token"]
H = {"Authorization": f"Bearer {TOKEN}", "Content-Type": "application/json"}

print("=" * 60)
print("  三国智能体端到端验证")
print("=" * 60)

# Test 1: List agents
print("\n--- Test 1: 智能体列表 ---")
r = requests.get(f"{BASE}/api/agent-management", headers=H, timeout=10)
print(f"Status: {r.status_code}")
agents_data = r.json()
if isinstance(agents_data, dict):
    agents = agents_data.get("agents", agents_data.get("items", []))
else:
    agents = agents_data if isinstance(agents_data, list) else []
print(f"Agents count: {len(agents)}")
for a in agents:
    print(f"  - {a.get('name', '?')} / {a.get('display_name', '?')} (id={a.get('agent_id', '?')})")

# Test 2: Entity types
print("\n--- Test 2: 三国实体类型 ---")
r = requests.get(f"{BASE}/api/ontology/model/entity-types", headers=H, timeout=10)
data = r.json()
if isinstance(data, dict):
    items = data.get("entity_types", data.get("types", data.get("items", [])))
else:
    items = data
sanguo_types = [t for t in items if "Sanguo" in t.get("name", "")]
print(f"Sanguo entity types: {len(sanguo_types)}")
type_id_map = {}
for t in sanguo_types:
    tid = t.get("type_id", "")
    type_id_map[t["name"]] = tid
    print(f"  {t['name']}: {tid}")

# Test 3: Character instances
print("\n--- Test 3: 三国人物实例 ---")
char_tid = type_id_map.get("SanguoCharacter", "")
if char_tid:
    r = requests.get(f"{BASE}/api/ontology/model/instances?type_id={char_tid}&page_size=5", headers=H, timeout=10)
    data = r.json()
    if isinstance(data, dict):
        insts = data.get("instances", data.get("items", []))
    else:
        insts = data if isinstance(data, list) else []
    print(f"Character instances (first 5): {len(insts)}")
    for i in insts[:5]:
        props = i.get("properties", {})
        if isinstance(props, str):
            try:
                props = json.loads(props)
            except:
                props = {}
        print(f"  - {props.get('name', '?')} ({props.get('faction', '?')})")

# Test 4: QA with short timeout (test RAG retrieval only)
print("\n--- Test 4: QA 问答 (5s超时) ---")
try:
    r = requests.post(f"{BASE}/api/qa/ask", headers=H, json={
        "question": "曹操是谁？",
        "workspace_id": "9faf2fa2-6109-4ab5-bd31-a113555649aa",
        "agent_id": "agent_3b10cedc5a03",
    }, timeout=5)
    print(f"Status: {r.status_code}")
    if r.status_code == 200:
        ans = r.json()
        print(f"Answer: {ans.get('answer', '')[:200]}")
        print(f"Sources: {len(ans.get('sources', []))}")
    else:
        print(f"Error: {r.text[:300]}")
except requests.exceptions.Timeout:
    print("TIMEOUT - QA引擎超时（LLM调用阻塞）")
except Exception as e:
    print(f"Error: {e}")

# Test 5: Agent dispatch
print("\n--- Test 5: Agent dispatch ---")
try:
    r = requests.post(f"{BASE}/api/agent/dispatch", headers=H, json={
        "intent": "查询三国人物曹操的信息",
        "context": {"workspace_id": "9faf2fa2-6109-4ab5-bd31-a113555649aa"},
        "workspace_id": "9faf2fa2-6109-4ab5-bd31-a113555649aa",
    }, timeout=10)
    print(f"Status: {r.status_code}")
    if r.status_code == 200:
        result = r.json()
        print(f"Task ID: {result.get('task_id')}")
        print(f"Agent: {result.get('assigned_agent')}")
        print(f"Confidence: {result.get('confidence')}")
        print(f"Plan: {json.dumps(result.get('plan', []), ensure_ascii=False)[:200]}")
    else:
        print(f"Error: {r.text[:300]}")
except Exception as e:
    print(f"Error: {e}")

# Test 6: Skills
print("\n--- Test 6: 技能列表 ---")
r = requests.get(f"{BASE}/api/skill/skills", headers=H, params={"page_size": 100}, timeout=10)
data = r.json()
if isinstance(data, dict):
    skills = data.get("skills", data.get("items", []))
else:
    skills = data if isinstance(data, list) else []
print(f"Skills count: {len(skills)}")
for s in skills:
    print(f"  - {s.get('name', s.get('skill_id', '?'))}: {s.get('description', '')[:50]}")

print("\n" + "=" * 60)
print("  验证完成")
print("=" * 60)
