"""端到端验证脚本2：测试QA和Agent dispatch"""
import requests
import time
import json

BASE = "http://localhost:8000"

r = requests.post(f"{BASE}/api/auth/login", json={"username": "admin", "password": "admin123"}, timeout=10)
TOKEN = r.json()["access_token"]
H = {"Authorization": f"Bearer {TOKEN}", "Content-Type": "application/json"}

# Test QA with 50s timeout
print("Testing QA ask (50s timeout)...")
start = time.time()
try:
    r = requests.post(f"{BASE}/api/qa/ask", headers=H, json={
        "question": "曹操是谁？",
        "workspace_id": "9faf2fa2-6109-4ab5-bd31-a113555649aa",
        "agent_id": "agent_3b10cedc5a03",
    }, timeout=50)
    elapsed = time.time() - start
    print(f"Status: {r.status_code} ({elapsed:.1f}s)")
    if r.status_code == 200:
        ans = r.json()
        answer = ans.get("answer", "")
        print(f"Answer: {answer[:300]}")
        print(f"Sources: {len(ans.get('sources', []))}")
    else:
        print(f"Error: {r.text[:300]}")
except requests.exceptions.Timeout:
    elapsed = time.time() - start
    print(f"TIMEOUT after {elapsed:.1f}s")
except Exception as e:
    elapsed = time.time() - start
    print(f"Error after {elapsed:.1f}s: {e}")

# Test Agent dispatch with 30s timeout
print()
print("Testing Agent dispatch (30s timeout)...")
start = time.time()
try:
    r = requests.post(f"{BASE}/api/agent/dispatch", headers=H, json={
        "intent": "查询三国人物曹操的信息",
        "context": {"workspace_id": "9faf2fa2-6109-4ab5-bd31-a113555649aa"},
        "workspace_id": "9faf2fa2-6109-4ab5-bd31-a113555649aa",
    }, timeout=30)
    elapsed = time.time() - start
    print(f"Status: {r.status_code} ({elapsed:.1f}s)")
    if r.status_code == 200:
        result = r.json()
        print(f"Task: {result.get('task_id')}")
        print(f"Agent: {result.get('assigned_agent')}")
        print(f"Confidence: {result.get('confidence')}")
    else:
        print(f"Error: {r.text[:300]}")
except requests.exceptions.Timeout:
    elapsed = time.time() - start
    print(f"TIMEOUT after {elapsed:.1f}s")
except Exception as e:
    elapsed = time.time() - start
    print(f"Error after {elapsed:.1f}s: {e}")

# Test sanguo skills directly
print()
print("Testing sanguo skills via API...")
try:
    r = requests.get(f"{BASE}/api/skill/skills", headers=H, params={"page_size": 100}, timeout=10)
    data = r.json()
    if isinstance(data, dict):
        skills = data.get("skills", data.get("items", []))
    else:
        skills = data if isinstance(data, list) else []
    sanguo_skills = [s for s in skills if "sanguo" in s.get("name", "").lower()]
    print(f"Sanguo skills: {len(sanguo_skills)}")
    for s in sanguo_skills:
        print(f"  - {s.get('name')}: {s.get('description', '')[:60]}")
except Exception as e:
    print(f"Error: {e}")
