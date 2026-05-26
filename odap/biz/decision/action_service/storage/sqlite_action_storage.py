import sqlite3
import json
import os
import uuid
from datetime import datetime, timezone
from typing import Dict, Any, List, Optional

DEFAULT_DB_DIR = os.environ.get("DATA_DIR", os.path.join(os.getcwd(), "data"))
DEFAULT_DB_PATH = os.path.join(DEFAULT_DB_DIR, "action_records.db")


class SQLiteActionStorage:
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
        c.execute('''CREATE TABLE IF NOT EXISTS action_records (
            action_record_id TEXT PRIMARY KEY,
            action_type_id TEXT NOT NULL,
            target_object_id TEXT NOT NULL,
            target_object_type TEXT NOT NULL,
            parameters TEXT DEFAULT '{}',
            status TEXT DEFAULT 'pending',
            requested_by TEXT DEFAULT 'system',
            reason TEXT DEFAULT '',
            agent_id TEXT,
            opa_decision TEXT,
            validation_result TEXT,
            execution_result TEXT,
            writeback_result TEXT,
            created_at TEXT NOT NULL,
            updated_at TEXT NOT NULL
        )''')
        c.execute('''CREATE INDEX IF NOT EXISTS idx_action_status ON action_records(status)''')
        c.execute('''CREATE INDEX IF NOT EXISTS idx_action_target ON action_records(target_object_id)''')
        c.execute('''CREATE INDEX IF NOT EXISTS idx_action_type ON action_records(action_type_id)''')
        conn.commit()
        conn.close()

    def _row_to_dict(self, row: sqlite3.Row) -> Dict[str, Any]:
        d = dict(row)
        for key in ('parameters', 'opa_decision', 'validation_result', 'execution_result', 'writeback_result'):
            val = d.get(key)
            if isinstance(val, str):
                try:
                    d[key] = json.loads(val)
                except (json.JSONDecodeError, TypeError):
                    d[key] = None
        return d

    def create_record(self, data: Dict[str, Any]) -> Dict[str, Any]:
        now = datetime.now(timezone.utc).isoformat()
        record_id = f"ar_{uuid.uuid4().hex[:12]}"
        record = {
            'action_record_id': record_id,
            'action_type_id': data.get('action_type_id', ''),
            'target_object_id': data.get('target_object_id', ''),
            'target_object_type': data.get('target_object_type', ''),
            'parameters': json.dumps(data.get('parameters', {}), ensure_ascii=False),
            'status': 'pending',
            'requested_by': data.get('requested_by', 'system'),
            'reason': data.get('reason', ''),
            'agent_id': data.get('agent_id'),
            'opa_decision': None,
            'validation_result': None,
            'execution_result': None,
            'writeback_result': None,
            'created_at': now,
            'updated_at': now,
        }
        conn = self._get_conn()
        try:
            cols = ', '.join(record.keys())
            placeholders = ', '.join(['?'] * len(record))
            conn.execute(f"INSERT INTO action_records ({cols}) VALUES ({placeholders})", list(record.values()))
            conn.commit()
            return self.get_record(record_id)
        finally:
            conn.close()

    def get_record(self, record_id: str) -> Optional[Dict[str, Any]]:
        conn = self._get_conn()
        try:
            row = conn.execute("SELECT * FROM action_records WHERE action_record_id = ?", (record_id,)).fetchone()
            if not row:
                return None
            return self._row_to_dict(row)
        finally:
            conn.close()

    def update_status(self, record_id: str, status: str, **kwargs) -> Optional[Dict[str, Any]]:
        existing = self.get_record(record_id)
        if not existing:
            return None
        now = datetime.now(timezone.utc).isoformat()
        sets = ["status = ?", "updated_at = ?"]
        values = [status, now]
        json_fields = ('opa_decision', 'validation_result', 'execution_result', 'writeback_result')
        for key, val in kwargs.items():
            if key in json_fields and val is not None:
                sets.append(f"{key} = ?")
                values.append(json.dumps(val, ensure_ascii=False))
            elif val is not None:
                sets.append(f"{key} = ?")
                values.append(val)
        values.append(record_id)
        conn = self._get_conn()
        try:
            conn.execute(f"UPDATE action_records SET {', '.join(sets)} WHERE action_record_id = ?", values)
            conn.commit()
            return self.get_record(record_id)
        finally:
            conn.close()

    def list_records(self, status: Optional[str] = None, limit: int = 50, offset: int = 0) -> List[Dict[str, Any]]:
        conn = self._get_conn()
        try:
            if status:
                rows = conn.execute(
                    "SELECT * FROM action_records WHERE status = ? ORDER BY created_at DESC LIMIT ? OFFSET ?",
                    (status, limit, offset)
                ).fetchall()
            else:
                rows = conn.execute(
                    "SELECT * FROM action_records ORDER BY created_at DESC LIMIT ? OFFSET ?",
                    (limit, offset)
                ).fetchall()
            return [self._row_to_dict(r) for r in rows]
        finally:
            conn.close()

    def list_by_target(self, target_object_id: str, limit: int = 20) -> List[Dict[str, Any]]:
        conn = self._get_conn()
        try:
            rows = conn.execute(
                "SELECT * FROM action_records WHERE target_object_id = ? ORDER BY created_at DESC LIMIT ?",
                (target_object_id, limit)
            ).fetchall()
            return [self._row_to_dict(r) for r in rows]
        finally:
            conn.close()
