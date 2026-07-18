"""三国战纪智能体完整闭环验证"""
import requests
import json
import time

BASE = "http://localhost:8000"

r = requests.post(f"{BASE}/api/auth/login", json={"username": "admin", "password": "admin123"}, timeout=10)
TOKEN = r.json()["access_token"]
H = {"Authorization": f"Bearer {TOKEN}", "Content-Type": "application/json"}

WS_ID = "9faf2fa2-6109-4ab5-bd31-a113555649aa"
AGENT_ID = "agent_3b10cedc5a03"

print("=" * 60)
print("  三国战纪智能体 - 完整闭环验证")
print("=" * 60)

# Test 1: QA - 人物查询
print("\n--- Test 1: QA - 曹操是谁？ ---")
start = time.time()
try:
    r = requests.post(f"{BASE}/api/qa/ask", headers=H, json={
        "question": "曹操是谁？",
        "workspace_id": WS_ID,
        "agent_id": AGENT_ID,
    }, timeout=50)
    elapsed = time.time() - start
    ans = r.json()
    answer = ans.get("answer", "")
    print(f"[{elapsed:.1f}s] {answer[:200]}")
except Exception as e:
    print(f"Error: {e}")

# Test 2: QA - 势力分析
print("\n--- Test 2: QA - 魏蜀吴三国势力 ---")
start = time.time()
try:
    r = requests.post(f"{BASE}/api/qa/ask", headers=H, json={
        "question": "三国演义中魏蜀吴三国的势力如何？",
        "workspace_id": WS_ID,
        "agent_id": AGENT_ID,
    }, timeout=50)
    elapsed = time.time() - start
    ans = r.json()
    answer = ans.get("answer", "")
    print(f"[{elapsed:.1f}s] {answer[:200]}")
except Exception as e:
    print(f"Error: {e}")

# Test 3: QA - 事件查询
print("\n--- Test 3: QA - 赤壁之战 ---")
start = time.time()
try:
    r = requests.post(f"{BASE}/api/qa/ask", headers=H, json={
        "question": "赤壁之战是怎么回事？",
        "workspace_id": WS_ID,
        "agent_id": AGENT_ID,
    }, timeout=50)
    elapsed = time.time() - start
    ans = r.json()
    answer = ans.get("answer", "")
    print(f"[{elapsed:.1f}s] {answer[:200]}")
except Exception as e:
    print(f"Error: {e}")

# Test 4: Agent dispatch - 三国查询路由
print("\n--- Test 4: Agent dispatch - 三国人物路由 ---")
start = time.time()
try:
    r = requests.post(f"{BASE}/api/agent/dispatch", headers=H, json={
        "intent": "查询三国人物诸葛亮的信息",
        "context": {"workspace_id": WS_ID},
        "workspace_id": WS_ID,
    }, timeout=30)
    elapsed = time.time() - start
    result = r.json()
    print(f"[{elapsed:.1f}s] Agent: {result.get('assigned_agent')}, Confidence: {result.get('confidence')}")
except Exception as e:
    print(f"Error: {e}")

# Test 5: Skill execution - sanguo_timeline
print("\n--- Test 5: Skill - sanguo_timeline (200-210年) ---")
start = time.time()
try:
    r = requests.post(f"{BASE}/api/skill/execute", headers=H, json={
        "skill_name": "sanguo_timeline",
        "parameters": {"start_year": 200, "end_year": 210},
    }, timeout=15)
    elapsed = time.time() - start
    result = r.json()
    if result.get("success"):
        data = result.get("data", {})
        timeline = data.get("timeline", {})
        print(f"[{elapsed:.1f}s] Timeline: {len(timeline)} years, {data.get('total_events', 0)} events")
        for year, events in sorted(timeline.items())[:5]:
            names = [e.get("name", "?") for e in events[:3]]
            print(f"  {year}年: {', '.join(names)}")
    else:
        print(f"[{elapsed:.1f}s] Error: {result.get('error', 'unknown')}")
except Exception as e:
    elapsed = time.time() - start
    print(f"[{elapsed:.1f}s] Error: {e}")

# Test 6: Skill execution - sanguo_faction_analysis
print("\n--- Test 6: Skill - sanguo_faction_analysis ---")
start = time.time()
try:
    r = requests.post(f"{BASE}/api/skill/execute", headers=H, json={
        "skill_name": "sanguo_faction_analysis",
        "parameters": {},
    }, timeout=15)
    elapsed = time.time() - start
    result = r.json()
    if result.get("success"):
        data = result.get("data", {})
        factions = data.get("factions", {})
        print(f"[{elapsed:.1f}s] Factions: {data.get('total_factions', 0)}, Characters: {data.get('total_characters', 0)}")
        for fid, info in factions.items():
            members = info.get("members", [])
            names = [m.get("name", "?") for m in members[:3]]
            print(f"  {fid}: {len(members)} members ({', '.join(names)}...)")
    else:
        print(f"[{elapsed:.1f}s] Error: {result.get('error', 'unknown')}")
except Exception as e:
    elapsed = time.time() - start
    print(f"[{elapsed:.1f}s] Error: {e}")

# Test 7: Skill execution - sanguo_character_query
print("\n--- Test 7: Skill - sanguo_character_query (蜀国) ---")
start = time.time()
try:
    r = requests.post(f"{BASE}/api/skill/execute", headers=H, json={
        "skill_name": "sanguo_character_query",
        "parameters": {"faction": "faction_shu"},
    }, timeout=15)
    elapsed = time.time() - start
    result = r.json()
    if result.get("success"):
        data = result.get("data", {})
        chars = data.get("characters", [])
        print(f"[{elapsed:.1f}s] Characters: {data.get('total', 0)}")
        for c in chars[:5]:
            print(f"  - {c.get('name', '?')} ({c.get('role', '?')}, {c.get('title', '?')})")
    else:
        print(f"[{elapsed:.1f}s] Error: {result.get('error', 'unknown')}")
except Exception as e:
    elapsed = time.time() - start
    print(f"[{elapsed:.1f}s] Error: {e}")

# Test 8: Skill execution - sanguo_event_query
print("\n--- Test 8: Skill - sanguo_event_query (战役) ---")
start = time.time()
try:
    r = requests.post(f"{BASE}/api/skill/execute", headers=H, json={
        "skill_name": "sanguo_event_query",
        "parameters": {"category": "战役"},
    }, timeout=15)
    elapsed = time.time() - start
    result = r.json()
    if result.get("success"):
        data = result.get("data", {})
        events = data.get("events", [])
        print(f"[{elapsed:.1f}s] Events: {data.get('total', 0)}")
        for e in events[:5]:
            print(f"  - {e.get('name', '?')} ({e.get('year', '?')}年, {e.get('location', '?')})")
    else:
        print(f"[{elapsed:.1f}s] Error: {result.get('error', 'unknown')}")
except Exception as e:
    elapsed = time.time() - start
    print(f"[{elapsed:.1f}s] Error: {e}")

print("\n" + "=" * 60)
print("  验证完成")
print("=" * 60)
