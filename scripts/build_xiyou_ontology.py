#!/usr/bin/env python3
"""构建西游记本体到 ODAP 平台

纯调平台 HTTP API，不依赖自定义客户端。
种子数据来自 scripts/xiyou_seed/。

执行流程:
  1. 登录 ODAP 平台
  2. 创建/获取工作空间 X
  3. 创建/获取场景 X-2
  4. 注册 7 个实体类型 (XiyouFaction/Character/Location/Event/Treasure/Spell/Relationship)
  5. 批量注入种子数据

运行:
  cd E:\DEMO\AI\ontology-graphiti
  python scripts/build_xiyou_ontology.py
"""
import sys
import os
import time
import json
import logging
import argparse

import requests

sys.path.insert(0, os.path.dirname(__file__))
from xiyou_seed import (
    FACTIONS, CHARACTERS, LOCATIONS, EVENTS,
    TREASURES, SPELLS, RELATIONSHIPS,
)

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
log = logging.getLogger("build_xiyou")


class PlatformAPI:
    """直接调平台 REST API"""

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
                           description: str = "", properties: list = None,
                           links: list = None, actions: list = None) -> dict:
        payload = {
            "name": name,
            "display_name": display_name or name,
            "description": description or f"西游业务实体类型: {name}",
            "properties": properties or [],
            "links": links or [],
            "actions": actions or [],
        }
        r = self._call("POST", "/api/ontology/model/entity-types", json=payload)
        if r.status_code == 500 and "already exists" in r.text:
            log.warning("entity type %s already exists, refetching", name)
            t = self.find_entity_type(name)
            if t:
                return t
        r.raise_for_status()
        return r.json()

    def batch_create_instances(self, type_id: str, items: list) -> dict:
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

    def create_agent(self, data: dict) -> dict:
        r = self._call("POST", "/api/agent-management", json=data)
        r.raise_for_status()
        return r.json()

    def list_agents(self) -> list:
        r = self._call("GET", "/api/agent-management")
        data = r.json()
        if isinstance(data, list):
            return data
        if isinstance(data, dict):
            return data.get("agents", data.get("items", []))
        return []


# ============================================================
# 实体类型定义（中英文 name + display_name）
# ============================================================

ENTITY_TYPE_DEFS = {
    "XiyouFaction": {
        "display_name": "西游势力",
        "description": "西游记中的四大势力（天庭/佛门/妖界/人间）",
        "properties": [
            {"name": "faction_id", "display_name": "势力ID", "data_type": "string", "is_required": True, "is_primary_key": True},
            {"name": "name", "display_name": "名称", "data_type": "string", "is_required": True},
            {"name": "full_name", "display_name": "全称", "data_type": "string"},
            {"name": "faction_type", "display_name": "势力类型", "data_type": "string"},
            {"name": "leader", "display_name": "首脑", "data_type": "string"},
            {"name": "domain", "display_name": "势力范围", "data_type": "string"},
            {"name": "description", "display_name": "描述", "data_type": "text"},
        ],
        "links": [
            {"name": "controls", "display_name": "掌管", "target_type": "XiyouLocation", "cardinality": "1:N"},
        ],
    },
    "XiyouCharacter": {
        "display_name": "西游人物",
        "description": "西游记中的主要人物（取经团队/妖魔/神仙/凡人）",
        "properties": [
            {"name": "character_id", "display_name": "人物ID", "data_type": "string", "is_required": True, "is_primary_key": True},
            {"name": "name", "display_name": "姓名", "data_type": "string", "is_required": True},
            {"name": "full_name", "display_name": "全称", "data_type": "string"},
            {"name": "dharma_name", "display_name": "法名", "data_type": "string"},
            {"name": "title", "display_name": "称号", "data_type": "string"},
            {"name": "race", "display_name": "种族", "data_type": "string"},
            {"name": "faction", "display_name": "势力归属", "data_type": "string"},
            {"name": "role", "display_name": "角色", "data_type": "string"},
            {"name": "cultivation", "display_name": "修为", "data_type": "string"},
            {"name": "description", "display_name": "描述", "data_type": "text"},
        ],
        "links": [
            {"name": "mentor_disciple", "display_name": "师徒", "target_type": "XiyouCharacter", "cardinality": "N:N"},
            {"name": "sworn_brother", "display_name": "结拜", "target_type": "XiyouCharacter", "cardinality": "N:N"},
            {"name": "enemy_of", "display_name": "敌对", "target_type": "XiyouCharacter", "cardinality": "N:N"},
            {"name": "belongs_to", "display_name": "隶属", "target_type": "XiyouFaction", "cardinality": "N:1"},
            {"name": "dwells_at", "display_name": "栖居于", "target_type": "XiyouLocation", "cardinality": "N:1"},
            {"name": "holds", "display_name": "持有", "target_type": "XiyouTreasure", "cardinality": "N:N"},
            {"name": "masters", "display_name": "掌握", "target_type": "XiyouSpell", "cardinality": "N:N"},
        ],
    },
    "XiyouLocation": {
        "display_name": "西游地点",
        "description": "西游记中的重要地理位置（仙山/洞府/国度/险境）",
        "properties": [
            {"name": "location_id", "display_name": "地点ID", "data_type": "string", "is_required": True, "is_primary_key": True},
            {"name": "name", "display_name": "名称", "data_type": "string", "is_required": True},
            {"name": "full_name", "display_name": "全称", "data_type": "string"},
            {"name": "location_type", "display_name": "地点类型", "data_type": "string"},
            {"name": "faction", "display_name": "所属势力", "data_type": "string"},
            {"name": "region", "display_name": "所属地域", "data_type": "string"},
            {"name": "danger_level", "display_name": "危险等级", "data_type": "integer"},
            {"name": "description", "display_name": "描述", "data_type": "text"},
        ],
        "links": [
            {"name": "controls", "display_name": "掌管", "target_type": "XiyouFaction", "cardinality": "N:1"},
        ],
    },
    "XiyouEvent": {
        "display_name": "西游事件",
        "description": "西游记中的关键情节（八十一难等）",
        "properties": [
            {"name": "event_id", "display_name": "事件ID", "data_type": "string", "is_required": True, "is_primary_key": True},
            {"name": "name", "display_name": "名称", "data_type": "string", "is_required": True},
            {"name": "chapter", "display_name": "回目", "data_type": "string"},
            {"name": "trial_number", "display_name": "难数", "data_type": "integer"},
            {"name": "category", "display_name": "类别", "data_type": "string"},
            {"name": "location", "display_name": "发生地点", "data_type": "string"},
            {"name": "description", "display_name": "描述", "data_type": "text"},
        ],
        "links": [
            {"name": "occurred_at", "display_name": "发生于", "target_type": "XiyouLocation", "cardinality": "N:1"},
            {"name": "participated_in", "display_name": "参与", "target_type": "XiyouCharacter", "cardinality": "N:N"},
        ],
    },
    "XiyouTreasure": {
        "display_name": "西游法宝",
        "description": "西游记中的法宝和兵器",
        "properties": [
            {"name": "treasure_id", "display_name": "法宝ID", "data_type": "string", "is_required": True, "is_primary_key": True},
            {"name": "name", "display_name": "名称", "data_type": "string", "is_required": True},
            {"name": "full_name", "display_name": "全称", "data_type": "string"},
            {"name": "treasure_type", "display_name": "类型", "data_type": "string"},
            {"name": "holder", "display_name": "持有者", "data_type": "string"},
            {"name": "origin", "display_name": "来源", "data_type": "string"},
            {"name": "power", "display_name": "威力", "data_type": "text"},
            {"name": "description", "display_name": "描述", "data_type": "text"},
        ],
        "links": [
            {"name": "holds", "display_name": "持有", "target_type": "XiyouCharacter", "cardinality": "N:N"},
        ],
    },
    "XiyouSpell": {
        "display_name": "西游法术",
        "description": "西游记中的法术和神通",
        "properties": [
            {"name": "spell_id", "display_name": "法术ID", "data_type": "string", "is_required": True, "is_primary_key": True},
            {"name": "name", "display_name": "名称", "data_type": "string", "is_required": True},
            {"name": "full_name", "display_name": "全称", "data_type": "string"},
            {"name": "spell_type", "display_name": "法术类型", "data_type": "string"},
            {"name": "master", "display_name": "掌握者", "data_type": "string"},
            {"name": "origin", "display_name": "来源", "data_type": "string"},
            {"name": "power", "display_name": "威力", "data_type": "text"},
            {"name": "description", "display_name": "描述", "data_type": "text"},
        ],
        "links": [
            {"name": "masters", "display_name": "掌握", "target_type": "XiyouCharacter", "cardinality": "N:N"},
        ],
    },
    "XiyouRelationship": {
        "display_name": "西游关系",
        "description": "西游记中人物之间的关系",
        "properties": [
            {"name": "rel_id", "display_name": "关系ID", "data_type": "string", "is_required": True, "is_primary_key": True},
            {"name": "type", "display_name": "关系类型", "data_type": "string", "is_required": True},
            {"name": "from", "display_name": "来源", "data_type": "string", "is_required": True},
            {"name": "to", "display_name": "目标", "data_type": "string", "is_required": True},
            {"name": "description", "display_name": "描述", "data_type": "text"},
        ],
    },
}


# ============================================================
# 数据转换
# ============================================================

def to_instance(data: dict) -> dict:
    # 关系数据用 type 作为 name
    name = data.get("name") or data.get("type", "")
    return {"name": name, "properties": {k: v for k, v in data.items() if k not in ("name", "type")}}


# ============================================================
# 主流程
# ============================================================

def main():
    parser = argparse.ArgumentParser(description="构建西游记本体")
    parser.add_argument("--base-url", default="http://localhost:8000")
    parser.add_argument("--workspace-name", default="X")
    parser.add_argument("--scenario-name", default="X-2")
    args = parser.parse_args()

    print("=" * 60)
    print("  西游记本体构建 (via Platform API)")
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
    log.info("Step 2: 创建/获取工作空间 %s", args.workspace_name)
    ws = api.get_or_create_workspace(args.workspace_name, "四大名著本体工作空间")
    ws_id = ws.get("workspace_id") or ws.get("id") or ws.get("ws_id")
    print(f"  ✓ workspace: {ws_id}")

    # Step 3: 场景
    log.info("Step 3: 创建/获取场景 %s", args.scenario_name)
    sc = api.get_or_create_scenario(ws_id, args.scenario_name, "西游记本体场景")
    sc_id = sc.get("scenario_id") or sc.get("id")
    print(f"  ✓ scenario: {sc_id}")

    # Step 4: 注册实体类型
    log.info("Step 4: 注册实体类型")
    type_ids = {}
    for name, defn in ENTITY_TYPE_DEFS.items():
        t = api.create_entity_type(
            name=name,
            display_name=defn["display_name"],
            description=defn["description"],
            properties=defn.get("properties", []),
            links=defn.get("links", []),
            actions=defn.get("actions", []),
        )
        tid = t.get("type_id") or t.get("id")
        type_ids[name] = tid
        print(f"  ✓ {name} ({defn['display_name']}): {tid}")

    # Step 5: 批量注入种子数据
    log.info("Step 5: 批量注入种子数据")

    def batch_inject(type_name, seed_data, label):
        tid = type_ids.get(type_name)
        if not tid:
            log.warning("  ⚠ %s 类型未找到，跳过", type_name)
            return 0
        instances = [to_instance(item) for item in seed_data]
        try:
            api.batch_create_instances(tid, instances)
            print(f"  ✓ {label}: {len(instances)} 条")
            return len(instances)
        except Exception as e:
            log.error("  ✗ %s 注入失败: %s", label, e)
            return 0

    total = 0
    total += batch_inject("XiyouFaction", FACTIONS, "势力")
    total += batch_inject("XiyouCharacter", CHARACTERS, "人物")
    total += batch_inject("XiyouLocation", LOCATIONS, "地点")
    total += batch_inject("XiyouEvent", EVENTS, "事件")
    total += batch_inject("XiyouTreasure", TREASURES, "法宝")
    total += batch_inject("XiyouSpell", SPELLS, "法术")
    total += batch_inject("XiyouRelationship", RELATIONSHIPS, "关系")

    print()
    print("=" * 60)
    print(f"  西游记本体构建完成！共注入 {total} 条种子数据")
    print(f"  场景: {sc_id}")
    print("=" * 60)

    # Step 6: 创建西游记智能体
    log.info("Step 6: 创建西游记智能体")
    # 先检查是否已存在
    existing = api.list_agents()
    _xiyou_agent_exists = any(
        a.get("name") == "xiyou_agent" or a.get("display_name") == "西游记智能体"
        for a in existing
    )
    if not _xiyou_agent_exists:
        try:
            agent_data = {
                "name": "xiyou_agent",
                "display_name": "西游记智能体",
                "avatar": "🐵",
                "description": "基于西游记本体的智能问答与推演智能体，涵盖八十一难、人物关系、法宝法术等知识",
                "main_object": type_ids.get("XiyouCharacter", ""),
                "related_objects": [
                    type_ids.get("XiyouFaction", ""),
                    type_ids.get("XiyouLocation", ""),
                    type_ids.get("XiyouEvent", ""),
                    type_ids.get("XiyouTreasure", ""),
                    type_ids.get("XiyouSpell", ""),
                    type_ids.get("XiyouRelationship", ""),
                ],
                "related_skills": [
                    "xiyou_timeline",
                    "xiyou_character_query",
                    "xiyou_treasure_query",
                    "xiyou_spell_query",
                ],
                "workspace_id": ws_id,
            }
            result = api.create_agent(agent_data)
            print(f"  ✓ 西游记智能体创建成功: {result.get('agent_id', result.get('id', ''))}")
        except Exception as e:
            log.warning("  ⚠ 智能体创建失败: %s", e)
    else:
        print("  ⚠ 西游记智能体已存在，跳过创建")


if __name__ == "__main__":
    main()
