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
from odap.biz.core.ontology.schema.domain import generate_oms_seed_data

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

            seed_data = generate_oms_seed_data()
            object_types = seed_data["object_types"]
            action_types = seed_data["action_types"]

            for type_name, type_def in object_types.items():
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

            for act in action_types:
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
