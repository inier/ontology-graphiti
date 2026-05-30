import sqlite3
import json
import os
from typing import Optional, List, Dict, Any


class SQLiteStateMachineStorage:
    def __init__(self, db_path=None):
        self.db_path = db_path or os.path.join(
            os.environ.get("DATA_DIR", os.path.join(os.getcwd(), "data")),
            "ontology_core.db"
        )
        self._init_db()

    def _init_db(self):
        conn = sqlite3.connect(self.db_path)
        c = conn.cursor()
        c.execute("""CREATE TABLE IF NOT EXISTS state_machines (
            sm_id TEXT PRIMARY KEY,
            name TEXT NOT NULL,
            description TEXT DEFAULT '',
            target_object_type TEXT NOT NULL,
            states TEXT DEFAULT '[]',
            transitions TEXT DEFAULT '[]',
            initial_state TEXT DEFAULT '',
            current_states TEXT DEFAULT '{}',
            bound_action_type_ids TEXT DEFAULT '[]',
            scenario_id TEXT,
            is_active INTEGER DEFAULT 1,
            created_at TEXT NOT NULL,
            updated_at TEXT NOT NULL
        )""")
        c.execute("CREATE INDEX IF NOT EXISTS idx_sm_object_type ON state_machines(target_object_type)")
        c.execute("CREATE INDEX IF NOT EXISTS idx_sm_scenario ON state_machines(scenario_id)")
        conn.commit()
        conn.close()

    def _ensure_json(self, value, default):
        if value is None:
            return json.dumps(default)
        if isinstance(value, str):
            return value
        return json.dumps(value)

    def save_state_machine(self, sm_data):
        conn = sqlite3.connect(self.db_path)
        c = conn.cursor()
        c.execute("""INSERT OR REPLACE INTO state_machines
            (sm_id, name, description, target_object_type, states, transitions,
             initial_state, current_states, bound_action_type_ids, scenario_id,
             is_active, created_at, updated_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (sm_data.get("sm_id"), sm_data.get("name", ""), sm_data.get("description", ""),
             sm_data.get("target_object_type", ""),
             self._ensure_json(sm_data.get("states"), []),
             self._ensure_json(sm_data.get("transitions"), []),
             sm_data.get("initial_state", ""),
             self._ensure_json(sm_data.get("current_states"), {}),
             self._ensure_json(sm_data.get("bound_action_type_ids"), []),
             sm_data.get("scenario_id"), 1 if sm_data.get("is_active", True) else 0,
             sm_data.get("created_at", ""), sm_data.get("updated_at", "")))
        conn.commit()
        conn.close()
        return sm_data

    def get_state_machine(self, sm_id):
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        c = conn.cursor()
        c.execute("SELECT * FROM state_machines WHERE sm_id = ?", (sm_id,))
        row = c.fetchone()
        conn.close()
        if not row:
            return None
        return dict(row)

    def get_state_machine_by_object_type(self, object_type):
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        c = conn.cursor()
        c.execute("SELECT * FROM state_machines WHERE target_object_type = ? AND is_active = 1", (object_type,))
        row = c.fetchone()
        conn.close()
        return dict(row) if row else None

    def list_state_machines(self, scenario_id=None, is_active=None):
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        c = conn.cursor()
        query = "SELECT * FROM state_machines WHERE 1=1"
        params = []
        if scenario_id:
            query += " AND scenario_id = ?"
            params.append(scenario_id)
        if is_active is not None:
            query += " AND is_active = ?"
            params.append(1 if is_active else 0)
        c.execute(query, params)
        rows = c.fetchall()
        conn.close()
        return [dict(r) for r in rows]

    def delete_state_machine(self, sm_id):
        conn = sqlite3.connect(self.db_path)
        c = conn.cursor()
        c.execute("DELETE FROM state_machines WHERE sm_id = ?", (sm_id,))
        affected = c.rowcount
        conn.commit()
        conn.close()
        return affected > 0
