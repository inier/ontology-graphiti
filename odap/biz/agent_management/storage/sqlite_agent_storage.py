import sqlite3
import json
import os
import uuid
from datetime import datetime, timezone
from typing import Dict, Any, List, Optional

DEFAULT_DB_DIR = os.environ.get("DATA_DIR", os.path.join(os.getcwd(), "data"))
DEFAULT_DB_PATH = os.path.join(DEFAULT_DB_DIR, "agents.db")


class SQLiteAgentStorage:
    def __init__(self, db_path: str = None):
        if db_path is None:
            os.makedirs(DEFAULT_DB_DIR, exist_ok=True)
            db_path = DEFAULT_DB_PATH
        self.db_path = db_path
        self._init_db()

    def _get_conn(self):
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        return conn

    def _init_db(self):
        conn = self._get_conn()
        c = conn.cursor()
        c.execute('''CREATE TABLE IF NOT EXISTS agents (
            agent_id TEXT PRIMARY KEY,
            name TEXT NOT NULL,
            display_name TEXT NOT NULL,
            avatar TEXT DEFAULT '',
            description TEXT DEFAULT '',
            main_object TEXT DEFAULT '',
            related_objects TEXT DEFAULT '[]',
            related_processes TEXT DEFAULT '[]',
            related_rules TEXT DEFAULT '[]',
            related_business_logic TEXT DEFAULT '[]',
            related_indicators TEXT DEFAULT '[]',
            related_skills TEXT DEFAULT '[]',
            related_knowledge_bases TEXT DEFAULT '[]',
            allowed_roles TEXT DEFAULT '[]',
            created_by TEXT DEFAULT 'system',
            created_at TEXT NOT NULL,
            updated_at TEXT NOT NULL
        )''')
        conn.commit()
        conn.close()

    def _row_to_dict(self, row: sqlite3.Row) -> Dict[str, Any]:
        d = dict(row)
        for key in [
            'related_objects', 'related_processes', 'related_rules',
            'related_business_logic', 'related_indicators',
            'related_skills', 'related_knowledge_bases', 'allowed_roles',
        ]:
            val = d.get(key, '[]')
            if isinstance(val, str):
                try:
                    d[key] = json.loads(val)
                except (json.JSONDecodeError, TypeError):
                    d[key] = []
            elif not isinstance(val, list):
                d[key] = []
        return d

    def list_agents(self, role_id: Optional[str] = None) -> List[Dict[str, Any]]:
        conn = self._get_conn()
        try:
            if role_id:
                rows = conn.execute(
                    "SELECT * FROM agents WHERE allowed_roles LIKE ?",
                    (f'%"{role_id}"%',),
                ).fetchall()
            else:
                rows = conn.execute("SELECT * FROM agents ORDER BY created_at DESC").fetchall()
            return [self._row_to_dict(r) for r in rows]
        finally:
            conn.close()

    def get_agent(self, agent_id: str) -> Optional[Dict[str, Any]]:
        conn = self._get_conn()
        try:
            row = conn.execute("SELECT * FROM agents WHERE agent_id = ?", (agent_id,)).fetchone()
            if not row:
                return None
            return self._row_to_dict(row)
        finally:
            conn.close()

    def create_agent(self, data: Dict[str, Any]) -> Dict[str, Any]:
        now = datetime.now(timezone.utc).isoformat()
        agent_id = f"agent_{uuid.uuid4().hex[:12]}"
        record = {
            'agent_id': agent_id,
            'name': data.get('name', ''),
            'display_name': data.get('display_name', ''),
            'avatar': data.get('avatar', ''),
            'description': data.get('description', ''),
            'main_object': data.get('main_object', ''),
            'related_objects': json.dumps(data.get('related_objects', []), ensure_ascii=False),
            'related_processes': json.dumps(data.get('related_processes', []), ensure_ascii=False),
            'related_rules': json.dumps(data.get('related_rules', []), ensure_ascii=False),
            'related_business_logic': json.dumps(data.get('related_business_logic', []), ensure_ascii=False),
            'related_indicators': json.dumps(data.get('related_indicators', []), ensure_ascii=False),
            'related_skills': json.dumps(data.get('related_skills', []), ensure_ascii=False),
            'related_knowledge_bases': json.dumps(data.get('related_knowledge_bases', []), ensure_ascii=False),
            'allowed_roles': json.dumps(data.get('allowed_roles', []), ensure_ascii=False),
            'created_by': data.get('created_by', 'system'),
            'created_at': now,
            'updated_at': now,
        }
        conn = self._get_conn()
        try:
            cols = ', '.join(record.keys())
            placeholders = ', '.join(['?'] * len(record))
            conn.execute(f"INSERT INTO agents ({cols}) VALUES ({placeholders})", list(record.values()))
            conn.commit()
            return self.get_agent(agent_id)
        finally:
            conn.close()

    def update_agent(self, agent_id: str, data: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        existing = self.get_agent(agent_id)
        if not existing:
            return None
        now = datetime.now(timezone.utc).isoformat()
        json_fields = [
            'related_objects', 'related_processes', 'related_rules',
            'related_business_logic', 'related_indicators',
            'related_skills', 'related_knowledge_bases', 'allowed_roles',
        ]
        sets = []
        values = []
        for key, val in data.items():
            if key in ('agent_id', 'created_at', 'created_by'):
                continue
            if key in json_fields and isinstance(val, list):
                sets.append(f"{key} = ?")
                values.append(json.dumps(val, ensure_ascii=False))
            elif val is not None:
                sets.append(f"{key} = ?")
                values.append(val)
        sets.append("updated_at = ?")
        values.append(now)
        values.append(agent_id)
        conn = self._get_conn()
        try:
            conn.execute(f"UPDATE agents SET {', '.join(sets)} WHERE agent_id = ?", values)
            conn.commit()
            return self.get_agent(agent_id)
        finally:
            conn.close()

    def delete_agent(self, agent_id: str) -> bool:
        existing = self.get_agent(agent_id)
        if not existing:
            return False
        conn = self._get_conn()
        try:
            conn.execute("DELETE FROM agents WHERE agent_id = ?", (agent_id,))
            conn.commit()
            return True
        finally:
            conn.close()
