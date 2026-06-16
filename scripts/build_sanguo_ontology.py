#!/usr/bin/env python3
"""构建三国演义本体到 ODAP 平台

纯调平台 HTTP API，不依赖自定义客户端。
种子数据来自 scripts/sanguo_seed/。

执行流程:
  1. 登录 ODAP 平台
  2. 创建/获取工作空间 X
  3. 创建/获取场景 X-1
  4. 注册 5 个实体类型 (SanguoFaction/Character/Location/Event/Relationship)
  5. 批量注入种子数据

运行:
  cd E:\\DEMO\\AI\\ontology-graphiti
  python scripts/build_sanguo_ontology.py
"""
import sys
import os
import time
import json
import logging
import argparse

import requests

# 种子数据
sys.path.insert(0, os.path.dirname(__file__))
from sanguo_seed import (
    FACTIONS, CHARACTERS, LOCATIONS, EVENTS, RELATIONSHIPS,
)

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
log = logging.getLogger("build_sanguo")


# ============================================================
# 平台 API 薄封装（仅本脚本使用，不复用）
# ============================================================

class PlatformAPI:
    """直接调平台 REST API，零自定义依赖"""

    def __init__(self, base_url: str):
        self.base = base_url.rstrip("/")
        self.token: str = ""
        self.s = requests.Session()

    def login(self, username: str = "admin", password: str = "admin123"):
        r = self.s.post(f"{self.base}/api/auth/login",
                        json={"username": username, "password": password}, timeout=10)
        r.raise_for_status()
        self.token = r.json()["access_token"]
        self.s.headers.update({"Authorization": f"Bearer {self.token}"})

    def _call(self, method: str, path: str, **kw):
        r = self.s.request(method, f"{self.base}{path}", timeout=15, **kw)
        if r.status_code >= 400:
            log.warning("%s %s -> %d %s", method, path, r.status_code, r.text[:200])
        return r

    def health(self) -> dict:
        return self._call("GET", "/health").json()

    # --- workspace ---
    def list_workspaces(self) -> list:
        r = self._call("GET", "/api/workspaces")
        data = r.json()
        if isinstance(data, dict):
            return data.get("workspaces", data.get("items", []))
        return data if isinstance(data, list) else []

    def find_workspace(self, name: str) -> dict | None:
        for ws in self.list_workspaces():
            if isinstance(ws, dict) and ws.get("name") == name:
                return ws
        return None

    def create_workspace(self, name: str, description: str = "") -> dict:
        r = self._call("POST", "/api/workspaces",
                       json={"name": name, "description": description})
        r.raise_for_status()
        return r.json()

    def get_or_create_workspace(self, name: str, desc: str = "") -> dict:
        ws = self.find_workspace(name)
        if ws:
            return ws
        return self.create_workspace(name, desc)

    # --- scenario ---
    def list_scenarios(self, ws_id: str) -> list:
        r = self._call("GET", f"/api/workspaces/{ws_id}/scenarios")
        data = r.json()
        if isinstance(data, dict):
            return data.get("scenarios", data.get("items", []))
        return data if isinstance(data, list) else []

    def find_scenario(self, ws_id: str, name: str) -> dict | None:
        for sc in self.list_scenarios(ws_id):
            if isinstance(sc, dict) and sc.get("name") == name:
                return sc
        return None

    def create_scenario(self, ws_id: str, name: str, desc: str = "") -> dict:
        r = self._call("POST", f"/api/workspaces/{ws_id}/scenarios",
                       json={"name": name, "description": desc})
        r.raise_for_status()
        return r.json()

    def get_or_create_scenario(self, ws_id: str, name: str, desc: str = "") -> dict:
        sc = self.find_scenario(ws_id, name)
        if sc:
            return sc
        return self.create_scenario(ws_id, name, desc)

    # --- entity types ---
    def list_entity_types(self) -> list:
        r = self._call("GET", "/api/ontology/model/entity-types")
        data = r.json()
        if isinstance(data, dict):
            for key in ("entity_types", "types", "items", "data"):
                if key in data and isinstance(data[key], list):
                    return data[key]
            return [data] if "name" in data else []
        return data if isinstance(data, list) else []

    def find_entity_type(self, name: str) -> dict | None:
        for t in self.list_entity_types():
            if isinstance(t, dict) and t.get("name") == name:
                return t
        return None

    def create_entity_type(self, name: str, display_name: str = "",
                           description: str = "", properties: list = None) -> dict:
        payload = {
            "name": name,
            "display_name": display_name or name,
            "description": description or f"三国业务实体类型: {name}",
            "properties": properties or [],
        }
        r = self._call("POST", "/api/ontology/model/entity-types", json=payload)
        if r.status_code in (500, 409) and "already exists" in r.text:
            log.warning("entity type %s already exists, refetching", name)
            t = self.find_entity_type(name)
            if t:
                return t
        r.raise_for_status()
        return r.json()

    # --- instances ---
    def batch_create_instances(self, type_id: str, items: list) -> dict:
        """批量创建实例，每个 item 自带 type_id + properties"""
        wrapped = []
        for it in items:
            props = dict(it.get("properties") or {})
            if "name" in it and "name" not in props:
                props["name"] = it["name"]
            wrapped.append({
                "type_id": type_id,
                "properties": props,
                "workspace_id": it.get("workspace_id", "default"),
            })
        r = self._call("POST", "/api/ontology/model/instances/batch",
                       json={"instances": wrapped})
        r.raise_for_status()
        return r.json()

    # --- agents ---
    def create_agent(self, data: dict) -> dict:
        r = self._call("POST", "/api/agents", json=data)
        r.raise_for_status()
        return r.json()

    def list_agents(self) -> list:
        r = self._call("GET", "/api/agents")
        data = r.json()
        if isinstance(data, list):
            return data
        if isinstance(data, dict):
            return data.get("agents", data.get("items", []))
        return []

    # --- skills ---
    def list_skills(self) -> list:
        r = self._call("GET", "/api/skill/skills", params={"page_size": 100})
        data = r.json()
        if isinstance(data, dict):
            return data.get("skills", data.get("items", []))
        return data if isinstance(data, list) else []


# ============================================================
# 实体类型定义
# ============================================================

ENTITY_TYPE_DEFS = {
    "SanguoFaction": {
        "display_name": "三国势力",
        "description": "三国鼎立时期的三大势力（魏蜀吴）及群雄",
        "properties": [
            {"name": "faction_id", "data_type": "string", "is_required": True, "is_primary_key": True},
            {"name": "name", "data_type": "string", "is_required": True},
            {"name": "full_name", "data_type": "string"},
            {"name": "founder", "data_type": "string"},
            {"name": "capital", "data_type": "string"},
            {"name": "established_year", "data_type": "integer"},
            {"name": "ended_year", "data_type": "integer"},
            {"name": "color", "data_type": "string"},
            {"name": "description", "data_type": "text"},
        ],
    },
    "SanguoCharacter": {
        "display_name": "三国人物",
        "description": "三国演义中的主要人物",
        "properties": [
            {"name": "character_id", "data_type": "string", "is_required": True, "is_primary_key": True},
            {"name": "name", "data_type": "string", "is_required": True},
            {"name": "faction", "data_type": "string"},
            {"name": "title", "data_type": "string"},
            {"name": "role", "data_type": "string"},
            {"name": "birth_year", "data_type": "integer"},
            {"name": "death_year", "data_type": "integer"},
            {"name": "origin", "data_type": "string"},
            {"name": "description", "data_type": "text"},
        ],
    },
    "SanguoLocation": {
        "display_name": "三国地点",
        "description": "三国时期的重要地理位置",
        "properties": [
            {"name": "location_id", "data_type": "string", "is_required": True, "is_primary_key": True},
            {"name": "name", "data_type": "string", "is_required": True},
            {"name": "faction", "data_type": "string"},
            {"name": "region", "data_type": "string"},
            {"name": "type", "data_type": "string"},
            {"name": "modern_location", "data_type": "string"},
            {"name": "description", "data_type": "text"},
        ],
    },
    "SanguoEvent": {
        "display_name": "三国事件",
        "description": "三国演义中的重大历史事件",
        "properties": [
            {"name": "event_id", "data_type": "string", "is_required": True, "is_primary_key": True},
            {"name": "name", "data_type": "string", "is_required": True},
            {"name": "year", "data_type": "integer", "is_required": True},
            {"name": "month", "data_type": "integer"},
            {"name": "category", "data_type": "string"},
            {"name": "location", "data_type": "string"},
            {"name": "description", "data_type": "text"},
        ],
    },
    "SanguoRelationship": {
        "display_name": "三国关系",
        "description": "三国人物之间的关系",
        "properties": [
            {"name": "rel_id", "data_type": "string", "is_required": True, "is_primary_key": True},
            {"name": "type", "data_type": "string", "is_required": True},
            {"name": "from", "data_type": "string", "is_required": True},
            {"name": "to", "data_type": "string", "is_required": True},
            {"name": "year", "data_type": "integer"},
            {"name": "description", "data_type": "text"},
        ],
    },
    "SanguoArtifact": {
        "display_name": "三国物品",
        "description": "三国演义中的兵器、坐骑、宝物等",
        "properties": [
            {"name": "artifact_id", "data_type": "string", "is_required": True, "is_primary_key": True},
            {"name": "name", "data_type": "string", "is_required": True},
            {"name": "full_name", "data_type": "string"},
            {"name": "artifact_type", "data_type": "string"},
            {"name": "holder", "data_type": "string"},
            {"name": "origin", "data_type": "string"},
            {"name": "description", "data_type": "text"},
        ],
    },
    "SanguoStrategy": {
        "display_name": "三国谋略",
        "description": "三国演义中的计策、兵法和阵法",
        "properties": [
            {"name": "strategy_id", "data_type": "string", "is_required": True, "is_primary_key": True},
            {"name": "name", "data_type": "string", "is_required": True},
            {"name": "full_name", "data_type": "string"},
            {"name": "strategy_type", "data_type": "string"},
            {"name": "devised_by", "data_type": "string"},
            {"name": "used_in_event", "data_type": "string"},
            {"name": "description", "data_type": "text"},
        ],
    },
}


# ============================================================
# 数据转换：种子数据 → 平台 instance 格式
# ============================================================

def faction_to_instance(f: dict) -> dict:
    return {"name": f["name"], "properties": {k: v for k, v in f.items() if k != "name"}}


def character_to_instance(c: dict) -> dict:
    return {"name": c["name"], "properties": {k: v for k, v in c.items() if k != "name"}}


def location_to_instance(loc: dict) -> dict:
    return {"name": loc["name"], "properties": {k: v for k, v in loc.items() if k != "name"}}


def event_to_instance(e: dict) -> dict:
    props = {k: v for k, v in e.items() if k not in ("name", "participants", "mentioned_characters")}
    # 列表字段序列化为 JSON 字符串存储
    if "participants" in e:
        props["participants"] = json.dumps(e["participants"], ensure_ascii=False)
    if "mentioned_characters" in e:
        props["mentioned_characters"] = json.dumps(e["mentioned_characters"], ensure_ascii=False)
    return {"name": e["name"], "properties": props}


def relationship_to_instance(r: dict) -> dict:
    return {"name": r.get("type", ""), "properties": {k: v for k, v in r.items() if k != "name"}}


# ============================================================
# 主流程
# ============================================================

def main():
    parser = argparse.ArgumentParser(description="构建三国演义本体")
    parser.add_argument("--base-url", default="http://localhost:8000")
    parser.add_argument("--workspace-name", default="X")
    parser.add_argument("--scenario-name", default="X-1")
    args = parser.parse_args()

    print("=" * 60)
    print("  三国演义本体构建 (via Platform API)")
    print("=" * 60)

    api = PlatformAPI(args.base_url)

    # Step 0: 健康检查
    log.info("Step 0: 平台健康检查")
    health = api.health()
    if health.get("status") != "healthy":
        log.error("平台不健康: %s", health)
        sys.exit(1)
    print("  ✓ 平台健康")

    # Step 1: 登录
    log.info("Step 1: 登录")
    api.login()
    print("  ✓ 登录成功")

    # Step 2: 工作空间
    log.info("Step 2: 创建工作空间 %s", args.workspace_name)
    ws = api.get_or_create_workspace(args.workspace_name, "三国演义本体测试工作空间")
    ws_id = ws.get("workspace_id") or ws.get("id") or ws.get("ws_id")
    print(f"  ✓ workspace: {ws_id}")

    # Step 3: 场景
    log.info("Step 3: 创建场景 %s", args.scenario_name)
    sc = api.get_or_create_scenario(ws_id, args.scenario_name, "三国演义本体场景")
    sc_id = sc.get("scenario_id") or sc.get("id")
    print(f"  ✓ scenario: {sc_id}")

    # Step 4: 注册实体类型
    log.info("Step 4: 注册实体类型")
    type_ids = {}
    for name, defn in ENTITY_TYPE_DEFS.items():
        t = api.create_entity_type(name=name, display_name=defn["display_name"],
                                   description=defn["description"],
                                   properties=defn["properties"])
        tid = t.get("type_id")
        type_ids[name] = tid
        print(f"  ✓ {name} -> {tid}")

    # Step 5: 注入数据
    log.info("Step 5: 注入种子数据")
    t0 = time.time()
    counts = {}

    # 势力
    items = [faction_to_instance(f) for f in FACTIONS]
    r = api.batch_create_instances(type_ids["SanguoFaction"], items)
    counts["factions"] = r.get("success", len(FACTIONS))
    print(f"  ✓ 势力: {counts['factions']}")

    # 人物
    items = [character_to_instance(c) for c in CHARACTERS]
    r = api.batch_create_instances(type_ids["SanguoCharacter"], items)
    counts["characters"] = r.get("success", len(CHARACTERS))
    print(f"  ✓ 人物: {counts['characters']}")

    # 地点
    items = [location_to_instance(loc) for loc in LOCATIONS]
    r = api.batch_create_instances(type_ids["SanguoLocation"], items)
    counts["locations"] = r.get("success", len(LOCATIONS))
    print(f"  ✓ 地点: {counts['locations']}")

    # 事件
    items = [event_to_instance(e) for e in EVENTS]
    r = api.batch_create_instances(type_ids["SanguoEvent"], items)
    counts["events"] = r.get("success", len(EVENTS))
    print(f"  ✓ 事件: {counts['events']}")

    # 关系
    items = [relationship_to_instance(rel) for rel in RELATIONSHIPS]
    r = api.batch_create_instances(type_ids["SanguoRelationship"], items)
    counts["relationships"] = r.get("success", len(RELATIONSHIPS))
    print(f"  ✓ 关系: {counts['relationships']}")

    elapsed = time.time() - t0
    total = sum(counts.values())

    print()
    print("=" * 60)
    print("  三国本体构建完成！")
    print("=" * 60)
    print(f"  耗时: {elapsed:.2f}s | 合计: {total} 个节点")
    for k, v in counts.items():
        print(f"  {k}: {v}")
    print()
    print("  接下来:")
    print("  1. 前端本体可视化: http://localhost:5173/ontology")
    print("  2. 创建三国战纪智能体: python scripts/create_sanguo_agent.py")
    print("  3. 智能问答: http://localhost:5173/my-agents")
    print()


if __name__ == "__main__":
    main()
