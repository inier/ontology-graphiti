import sqlite3
import json
import os
import uuid
from datetime import datetime, timezone
from typing import Dict, Any, List, Optional

from ..schemas import (
    ObjectTypeDefinition, ActionTypeDefinition, LinkDefinition,
    PropertyDefinition, ActionParameter,
)
from odap.biz.core.ontology.schema.domain import ENTITY_TYPES

DEFAULT_DB_DIR = os.environ.get("DATA_DIR", os.path.join(os.getcwd(), "data"))
DEFAULT_DB_PATH = os.path.join(DEFAULT_DB_DIR, "ontology_schema.db")


class SQLiteOMSStorage:
    def __init__(self, db_path: str = None):
        if db_path is None:
            os.makedirs(DEFAULT_DB_DIR, exist_ok=True)
            db_path = DEFAULT_DB_PATH
        self.db_path = db_path
        self._init_db()
        self._seed_from_domain()

    def _get_conn(self):
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        return conn

    def _init_db(self):
        conn = self._get_conn()
        c = conn.cursor()
        c.execute('''CREATE TABLE IF NOT EXISTS object_types (
            type_id TEXT PRIMARY KEY,
            name TEXT NOT NULL,
            display_name TEXT DEFAULT '',
            description TEXT DEFAULT '',
            properties TEXT DEFAULT '[]',
            links TEXT DEFAULT '[]',
            actions TEXT DEFAULT '[]',
            icon TEXT DEFAULT '',
            color TEXT DEFAULT '',
            is_active INTEGER DEFAULT 1,
            parent_type TEXT,
            created_at TEXT NOT NULL,
            updated_at TEXT NOT NULL
        )''')
        c.execute('''CREATE TABLE IF NOT EXISTS action_types (
            action_type_id TEXT PRIMARY KEY,
            name TEXT NOT NULL,
            display_name TEXT DEFAULT '',
            description TEXT DEFAULT '',
            target_object_type TEXT NOT NULL,
            parameters TEXT DEFAULT '[]',
            opa_policy TEXT,
            required_roles TEXT DEFAULT '[]',
            writeback_config TEXT,
            confirmation_required INTEGER DEFAULT 0,
            is_active INTEGER DEFAULT 1,
            created_at TEXT NOT NULL,
            updated_at TEXT NOT NULL
        )''')
        conn.commit()
        conn.close()

    def _seed_from_domain(self):
        conn = self._get_conn()
        try:
            count = conn.execute("SELECT COUNT(*) FROM object_types").fetchone()[0]
            if count > 0:
                return
            now = datetime.now(timezone.utc).isoformat()

            ADR036_OBJECT_TYPES = {
                "Unit": {
                    "display_name": "单位",
                    "description": "军事或组织单位",
                    "basic_properties": [
                        {"name": "unit_id", "display_name": "单位ID", "property_type": "string", "required": True},
                        {"name": "name", "display_name": "名称", "property_type": "string", "required": True},
                        {"name": "side", "display_name": "阵营", "property_type": "string", "required": True,
                         "enum_values": ["red", "blue", "neutral"]},
                        {"name": "unit_type", "display_name": "单位类型", "property_type": "string", "required": True,
                         "enum_values": ["infantry", "armor", "artillery", "air", "naval", "special"]},
                        {"name": "status", "display_name": "状态", "property_type": "string",
                         "enum_values": ["active", "deployed", "resting", "destroyed", "unknown"]},
                        {"name": "location", "display_name": "位置", "property_type": "string"},
                        {"name": "coordinates", "display_name": "坐标", "property_type": "geopoint"},
                    ],
                    "statistical_properties": [
                        {"name": "combat_power", "display_name": "战斗力", "property_type": "integer"},
                        {"name": "morale", "display_name": "士气", "property_type": "float"},
                        {"name": "supply_level", "display_name": "补给水平", "property_type": "float"},
                        {"name": "casualty_rate", "display_name": "伤亡率", "property_type": "float"},
                        {"name": "strength", "display_name": "兵力", "property_type": "integer"},
                    ],
                    "capabilities": [
                        {"name": "range", "display_name": "射程", "property_type": "float"},
                        {"name": "armor_penetration", "display_name": "穿甲能力", "property_type": "float"},
                        {"name": "air_defense", "display_name": "防空能力", "property_type": "float"},
                    ],
                    "constraints": [
                        {"name": "max_speed", "display_name": "最大速度", "property_type": "float"},
                        {"name": "min_supply", "display_name": "最低补给", "property_type": "float"},
                    ],
                    "links": [
                        {"name": "located_at", "display_name": "驻扎于", "target_type": "Location", "cardinality": "N:1"},
                        {"name": "attached_to", "display_name": "隶属于", "target_type": "Unit", "cardinality": "N:1"},
                        {"name": "engaged_with", "display_name": "交战中", "target_type": "Unit", "cardinality": "N:N"},
                    ],
                    "actions": ["move", "attack", "defend", "reinforce", "retreat"],
                },
                "Location": {
                    "display_name": "位置",
                    "description": "地理位置或区域",
                    "basic_properties": [
                        {"name": "location_id", "display_name": "位置ID", "property_type": "string", "required": True},
                        {"name": "name", "display_name": "名称", "property_type": "string", "required": True},
                        {"name": "location_type", "display_name": "位置类型", "property_type": "string",
                         "enum_values": ["zone", "sector", "point", "area"]},
                        {"name": "coordinates", "display_name": "坐标", "property_type": "geopoint"},
                        {"name": "parent_location", "display_name": "上级位置", "property_type": "string"},
                        {"name": "classification", "display_name": "分类", "property_type": "string"},
                    ],
                    "statistical_properties": [],
                    "capabilities": [],
                    "constraints": [],
                    "links": [
                        {"name": "adjacent_to", "display_name": "相邻", "target_type": "Location", "cardinality": "N:N"},
                        {"name": "contains", "display_name": "包含", "target_type": "Unit", "cardinality": "1:N"},
                    ],
                    "actions": [],
                },
                "Equipment": {
                    "display_name": "装备",
                    "description": "武器系统或装备",
                    "basic_properties": [
                        {"name": "equipment_id", "display_name": "装备ID", "property_type": "string", "required": True},
                        {"name": "name", "display_name": "名称", "property_type": "string", "required": True},
                        {"name": "equipment_type", "display_name": "装备类型", "property_type": "string",
                         "enum_values": ["vehicle", "weapon", "sensor", "communication", "protection"]},
                        {"name": "operational_status", "display_name": "运行状态", "property_type": "string",
                         "enum_values": ["operational", "degraded", "non_operational"]},
                    ],
                    "statistical_properties": [],
                    "capabilities": [
                        {"name": "range", "display_name": "射程", "property_type": "float"},
                        {"name": "accuracy", "display_name": "精度", "property_type": "float"},
                    ],
                    "constraints": [],
                    "links": [
                        {"name": "assigned_to", "display_name": "分配给", "target_type": "Unit", "cardinality": "N:1"},
                    ],
                    "actions": [],
                },
                "Event": {
                    "display_name": "事件",
                    "description": "领域事件",
                    "basic_properties": [
                        {"name": "event_id", "display_name": "事件ID", "property_type": "string", "required": True},
                        {"name": "event_type", "display_name": "事件类型", "property_type": "string",
                         "enum_values": ["contact", "attack", "movement", "communication", "observation"]},
                        {"name": "timestamp", "display_name": "时间戳", "property_type": "datetime", "required": True},
                        {"name": "location", "display_name": "位置", "property_type": "string"},
                        {"name": "description", "display_name": "描述", "property_type": "string"},
                        {"name": "phase", "display_name": "阶段", "property_type": "string"},
                    ],
                    "statistical_properties": [],
                    "capabilities": [],
                    "constraints": [],
                    "links": [
                        {"name": "participants", "display_name": "参与方", "target_type": "Unit", "cardinality": "N:N"},
                        {"name": "occurs_at", "display_name": "发生于", "target_type": "Location", "cardinality": "N:1"},
                    ],
                    "actions": ["observe", "communicate"],
                },
            }

            for type_name, type_def in ADR036_OBJECT_TYPES.items():
                all_props = []
                for category in ("basic_properties", "statistical_properties", "capabilities", "constraints"):
                    for p in type_def.get(category, []):
                        prop = dict(p)
                        prop["category"] = category
                        all_props.append(prop)

                links = []
                for l in type_def.get("links", []):
                    links.append({
                        "name": l["name"],
                        "display_name": l.get("display_name", l["name"].replace("_", " ").title()),
                        "source_type": type_name,
                        "target_type": l["target_type"],
                        "cardinality": l.get("cardinality", "N:N"),
                    })

                conn.execute(
                    "INSERT OR IGNORE INTO object_types (type_id, name, display_name, description, properties, links, actions, is_active, created_at, updated_at) VALUES (?,?,?,?,?,?,?,?,?,?)",
                    (type_name, type_name, type_def.get("display_name", type_name),
                     type_def.get("description", f"{type_name} object type"),
                     json.dumps(all_props, ensure_ascii=False),
                     json.dumps(links, ensure_ascii=False),
                     json.dumps(type_def.get("actions", []), ensure_ascii=False),
                     1, now, now)
                )

            ADR036_ACTION_TYPES = [
                {
                    "action_type_id": "move",
                    "name": "move",
                    "display_name": "移动",
                    "description": "将单位移动到指定位置",
                    "target_object_type": "Unit",
                    "parameters": [
                        {"name": "destination", "display_name": "目标位置", "param_type": "string", "required": True},
                        {"name": "speed", "display_name": "速度", "param_type": "float", "required": False},
                    ],
                    "required_roles": ["commander", "operator"],
                    "confirmation_required": False,
                },
                {
                    "action_type_id": "attack",
                    "name": "attack",
                    "display_name": "攻击",
                    "description": "对目标发起攻击",
                    "target_object_type": "Unit",
                    "parameters": [
                        {"name": "target_id", "display_name": "目标ID", "param_type": "string", "required": True},
                        {"name": "weapon_type", "display_name": "武器类型", "param_type": "string", "required": False},
                    ],
                    "opa_policy": "policies/attack/authorize",
                    "required_roles": ["commander"],
                    "confirmation_required": True,
                },
                {
                    "action_type_id": "defend",
                    "name": "defend",
                    "display_name": "防御",
                    "description": "在当前位置建立防御",
                    "target_object_type": "Unit",
                    "parameters": [
                        {"name": "defense_type", "display_name": "防御类型", "param_type": "string", "required": False,
                         "enum_values": ["perimeter", "point", "mobile"]},
                    ],
                    "required_roles": ["commander", "operator"],
                    "confirmation_required": False,
                },
                {
                    "action_type_id": "reinforce",
                    "name": "reinforce",
                    "display_name": "增援",
                    "description": "向目标位置增派兵力",
                    "target_object_type": "Unit",
                    "parameters": [
                        {"name": "reinforcement_type", "display_name": "增援类型", "param_type": "string", "required": False},
                        {"name": "units", "display_name": "增援单位", "param_type": "json", "required": False},
                    ],
                    "required_roles": ["commander"],
                    "confirmation_required": True,
                },
                {
                    "action_type_id": "retreat",
                    "name": "retreat",
                    "display_name": "撤退",
                    "description": "从当前位置撤退",
                    "target_object_type": "Unit",
                    "parameters": [
                        {"name": "destination", "display_name": "撤退目标", "param_type": "string", "required": True},
                        {"name": "orderly", "display_name": "有序撤退", "param_type": "boolean", "required": False},
                    ],
                    "required_roles": ["commander"],
                    "confirmation_required": True,
                },
                {
                    "action_type_id": "observe",
                    "name": "observe",
                    "display_name": "观察",
                    "description": "对目标区域进行观察",
                    "target_object_type": "Event",
                    "parameters": [
                        {"name": "area", "display_name": "观察区域", "param_type": "string", "required": True},
                        {"name": "duration", "display_name": "持续时间", "param_type": "float", "required": False},
                    ],
                    "required_roles": ["intelligence_officer", "operator"],
                    "confirmation_required": False,
                },
                {
                    "action_type_id": "communicate",
                    "name": "communicate",
                    "display_name": "通信",
                    "description": "发送或接收通信",
                    "target_object_type": "Event",
                    "parameters": [
                        {"name": "recipient", "display_name": "接收方", "param_type": "string", "required": True},
                        {"name": "message", "display_name": "消息内容", "param_type": "string", "required": True},
                        {"name": "priority", "display_name": "优先级", "param_type": "string", "required": False,
                         "enum_values": ["routine", "priority", "immediate", "flash"]},
                    ],
                    "required_roles": ["operator"],
                    "confirmation_required": False,
                },
            ]

            for act in ADR036_ACTION_TYPES:
                conn.execute(
                    "INSERT OR IGNORE INTO action_types (action_type_id, name, display_name, description, target_object_type, parameters, opa_policy, required_roles, confirmation_required, is_active, created_at, updated_at) VALUES (?,?,?,?,?,?,?,?,?,?,?,?)",
                    (act["action_type_id"], act["name"], act.get("display_name", act["name"]),
                     act.get("description", ""), act["target_object_type"],
                     json.dumps(act.get("parameters", []), ensure_ascii=False),
                     act.get("opa_policy"),
                     json.dumps(act.get("required_roles", []), ensure_ascii=False),
                     1 if act.get("confirmation_required", False) else 0,
                     1, now, now)
                )

            conn.commit()
        finally:
            conn.close()

    @staticmethod
    def _map_property_type(ptype: str) -> str:
        mapping = {
            "string": "string", "str": "string",
            "integer": "integer", "int": "integer",
            "float": "float", "number": "float",
            "boolean": "boolean", "bool": "boolean",
            "datetime": "datetime", "date": "datetime",
            "tuple": "geopoint", "coordinates": "geopoint",
            "list": "json", "dict": "json",
        }
        return mapping.get(ptype.lower(), "string")

    def _row_to_object_type(self, row: sqlite3.Row) -> Dict[str, Any]:
        d = dict(row)
        d['is_active'] = bool(d.get('is_active', 1))
        for key in ('properties', 'links', 'actions'):
            val = d.get(key, '[]')
            if isinstance(val, str):
                try:
                    d[key] = json.loads(val)
                except (json.JSONDecodeError, TypeError):
                    d[key] = []
        return d

    def _row_to_action_type(self, row: sqlite3.Row) -> Dict[str, Any]:
        d = dict(row)
        d['is_active'] = bool(d.get('is_active', 1))
        d['confirmation_required'] = bool(d.get('confirmation_required', 0))
        for key in ('parameters', 'required_roles'):
            val = d.get(key, '[]')
            if isinstance(val, str):
                try:
                    d[key] = json.loads(val)
                except (json.JSONDecodeError, TypeError):
                    d[key] = []
        if 'writeback_config' in d and isinstance(d['writeback_config'], str):
            try:
                d['writeback_config'] = json.loads(d['writeback_config'])
            except (json.JSONDecodeError, TypeError):
                d['writeback_config'] = None
        return d

    # Object Type CRUD
    def list_object_types(self, active_only: bool = True) -> List[Dict[str, Any]]:
        conn = self._get_conn()
        try:
            if active_only:
                rows = conn.execute("SELECT * FROM object_types WHERE is_active = 1 ORDER BY name").fetchall()
            else:
                rows = conn.execute("SELECT * FROM object_types ORDER BY name").fetchall()
            return [self._row_to_object_type(r) for r in rows]
        finally:
            conn.close()

    def get_object_type(self, type_id: str) -> Optional[Dict[str, Any]]:
        conn = self._get_conn()
        try:
            row = conn.execute("SELECT * FROM object_types WHERE type_id = ?", (type_id,)).fetchone()
            if not row:
                return None
            return self._row_to_object_type(row)
        finally:
            conn.close()

    def create_object_type(self, data: Dict[str, Any]) -> Dict[str, Any]:
        now = datetime.now(timezone.utc).isoformat()
        type_id = data.get('type_id', f"ot_{uuid.uuid4().hex[:12]}")
        record = {
            'type_id': type_id,
            'name': data.get('name', ''),
            'display_name': data.get('display_name', data.get('name', '')),
            'description': data.get('description', ''),
            'properties': json.dumps(data.get('properties', []), ensure_ascii=False),
            'links': json.dumps(data.get('links', []), ensure_ascii=False),
            'actions': json.dumps(data.get('actions', []), ensure_ascii=False),
            'icon': data.get('icon', ''),
            'color': data.get('color', ''),
            'is_active': 1,
            'parent_type': data.get('parent_type'),
            'created_at': now,
            'updated_at': now,
        }
        conn = self._get_conn()
        try:
            cols = ', '.join(record.keys())
            placeholders = ', '.join(['?'] * len(record))
            conn.execute(f"INSERT INTO object_types ({cols}) VALUES ({placeholders})", list(record.values()))
            conn.commit()
            return self.get_object_type(type_id)
        finally:
            conn.close()

    def update_object_type(self, type_id: str, data: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        existing = self.get_object_type(type_id)
        if not existing:
            return None
        now = datetime.now(timezone.utc).isoformat()
        json_fields = ('properties', 'links', 'actions')
        sets = []
        values = []
        for key, val in data.items():
            if key in ('type_id', 'created_at'):
                continue
            if key in json_fields and isinstance(val, list):
                sets.append(f"{key} = ?")
                values.append(json.dumps(val, ensure_ascii=False))
            elif val is not None:
                sets.append(f"{key} = ?")
                values.append(val)
        sets.append("updated_at = ?")
        values.append(now)
        values.append(type_id)
        conn = self._get_conn()
        try:
            conn.execute(f"UPDATE object_types SET {', '.join(sets)} WHERE type_id = ?", values)
            conn.commit()
            return self.get_object_type(type_id)
        finally:
            conn.close()

    def delete_object_type(self, type_id: str) -> bool:
        existing = self.get_object_type(type_id)
        if not existing:
            return False
        conn = self._get_conn()
        try:
            conn.execute("DELETE FROM object_types WHERE type_id = ?", (type_id,))
            conn.commit()
            return True
        finally:
            conn.close()

    # Action Type CRUD
    def list_action_types(self, target_type: Optional[str] = None) -> List[Dict[str, Any]]:
        conn = self._get_conn()
        try:
            if target_type:
                rows = conn.execute("SELECT * FROM action_types WHERE target_object_type = ? AND is_active = 1 ORDER BY name", (target_type,)).fetchall()
            else:
                rows = conn.execute("SELECT * FROM action_types WHERE is_active = 1 ORDER BY name").fetchall()
            return [self._row_to_action_type(r) for r in rows]
        finally:
            conn.close()

    def get_action_type(self, action_type_id: str) -> Optional[Dict[str, Any]]:
        conn = self._get_conn()
        try:
            row = conn.execute("SELECT * FROM action_types WHERE action_type_id = ?", (action_type_id,)).fetchone()
            if not row:
                return None
            return self._row_to_action_type(row)
        finally:
            conn.close()

    def create_action_type(self, data: Dict[str, Any]) -> Dict[str, Any]:
        now = datetime.now(timezone.utc).isoformat()
        action_type_id = data.get('action_type_id', f"act_{uuid.uuid4().hex[:12]}")
        record = {
            'action_type_id': action_type_id,
            'name': data.get('name', ''),
            'display_name': data.get('display_name', data.get('name', '')),
            'description': data.get('description', ''),
            'target_object_type': data.get('target_object_type', ''),
            'parameters': json.dumps(data.get('parameters', []), ensure_ascii=False),
            'opa_policy': data.get('opa_policy'),
            'required_roles': json.dumps(data.get('required_roles', []), ensure_ascii=False),
            'writeback_config': json.dumps(data.get('writeback_config'), ensure_ascii=False) if data.get('writeback_config') else None,
            'confirmation_required': 1 if data.get('confirmation_required', False) else 0,
            'is_active': 1,
            'created_at': now,
            'updated_at': now,
        }
        conn = self._get_conn()
        try:
            cols = ', '.join(record.keys())
            placeholders = ', '.join(['?'] * len(record))
            conn.execute(f"INSERT INTO action_types ({cols}) VALUES ({placeholders})", list(record.values()))
            conn.commit()
            return self.get_action_type(action_type_id)
        finally:
            conn.close()

    def update_action_type(self, action_type_id: str, data: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        existing = self.get_action_type(action_type_id)
        if not existing:
            return None
        now = datetime.now(timezone.utc).isoformat()
        json_fields = ('parameters', 'required_roles', 'writeback_config')
        sets = []
        values = []
        for key, val in data.items():
            if key in ('action_type_id', 'created_at'):
                continue
            if key in json_fields and val is not None:
                sets.append(f"{key} = ?")
                values.append(json.dumps(val, ensure_ascii=False))
            elif key == 'confirmation_required' and val is not None:
                sets.append(f"{key} = ?")
                values.append(1 if val else 0)
            elif val is not None:
                sets.append(f"{key} = ?")
                values.append(val)
        sets.append("updated_at = ?")
        values.append(now)
        values.append(action_type_id)
        conn = self._get_conn()
        try:
            conn.execute(f"UPDATE action_types SET {', '.join(sets)} WHERE action_type_id = ?", values)
            conn.commit()
            return self.get_action_type(action_type_id)
        finally:
            conn.close()

    def delete_action_type(self, action_type_id: str) -> bool:
        conn = self._get_conn()
        try:
            row = conn.execute("SELECT * FROM action_types WHERE action_type_id = ?", (action_type_id,)).fetchone()
            if not row:
                return False
            conn.execute("DELETE FROM action_types WHERE action_type_id = ?", (action_type_id,))
            conn.commit()
            return True
        finally:
            conn.close()

    def bind_action_to_object_type(self, type_id: str, action_type_id: str) -> bool:
        obj = self.get_object_type(type_id)
        if not obj:
            return False
        act = self.get_action_type(action_type_id)
        if not act:
            return False
        actions = obj.get('actions', [])
        if action_type_id not in actions:
            actions.append(action_type_id)
        return self.update_object_type(type_id, {'actions': actions}) is not None

    def unbind_action_from_object_type(self, type_id: str, action_type_id: str) -> bool:
        obj = self.get_object_type(type_id)
        if not obj:
            return False
        actions = obj.get('actions', [])
        if action_type_id in actions:
            actions.remove(action_type_id)
        return self.update_object_type(type_id, {'actions': actions}) is not None
