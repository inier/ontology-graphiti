import json
import os
import sqlite3
import uuid
from datetime import datetime
from typing import Any, Dict, List, Optional


DEFAULT_INGEST_TASK_DB_DIR = os.environ.get("DATA_DIR", os.path.join(os.getcwd(), "data"))
DEFAULT_INGEST_TASK_DB_PATH = os.path.join(DEFAULT_INGEST_TASK_DB_DIR, "ingestion_tasks.db")


class SQLiteIngestTaskStorage:
    def __init__(self, db_path: str = None):
        if db_path is None:
            os.makedirs(DEFAULT_INGEST_TASK_DB_DIR, exist_ok=True)
            db_path = DEFAULT_INGEST_TASK_DB_PATH
        self.db_path = db_path
        self._init_db()

    def _init_db(self):
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS ingest_tasks (
                task_id TEXT PRIMARY KEY,
                workspace_id TEXT NOT NULL,
                file_name TEXT,
                file_type TEXT,
                storage_key TEXT,
                status TEXT NOT NULL DEFAULT 'pending',
                source TEXT DEFAULT 'upload',
                process_steps TEXT DEFAULT '[]',
                transform_rules TEXT DEFAULT '[]',
                extracted_text TEXT,
                extracted_tables TEXT,
                error_message TEXT,
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL
            )
        ''')
        conn.commit()
        conn.close()

    def save_task(self, task: Dict[str, Any]) -> None:
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        cursor.execute('''
            INSERT OR REPLACE INTO ingest_tasks
            (task_id, workspace_id, file_name, file_type, storage_key, status,
             source, process_steps, transform_rules, extracted_text, extracted_tables,
             error_message, created_at, updated_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        ''', (
            task.get("task_id"),
            task.get("workspace_id"),
            task.get("file_name"),
            task.get("file_type"),
            task.get("storage_key"),
            task.get("status", "pending"),
            task.get("source", "upload"),
            json.dumps(task.get("process_steps", []), ensure_ascii=False),
            json.dumps(task.get("transform_rules", []), ensure_ascii=False),
            task.get("extracted_text"),
            json.dumps(task.get("extracted_tables", []), ensure_ascii=False),
            task.get("error_message"),
            task.get("created_at", datetime.now().isoformat()),
            task.get("updated_at", datetime.now().isoformat()),
        ))
        conn.commit()
        conn.close()

    def get_task(self, task_id: str) -> Optional[Dict[str, Any]]:
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        cursor.execute('SELECT * FROM ingest_tasks WHERE task_id = ?', (task_id,))
        row = cursor.fetchone()
        conn.close()
        if not row:
            return None
        d = dict(row)
        d["process_steps"] = json.loads(d.get("process_steps") or "[]")
        d["transform_rules"] = json.loads(d.get("transform_rules") or "[]")
        d["extracted_tables"] = json.loads(d.get("extracted_tables") or "[]")
        return d

    def update_task(self, task_id: str, updates: Dict[str, Any]) -> bool:
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        json_keys = {"process_steps", "transform_rules", "extracted_tables"}
        set_clause = []
        params = []
        for key, value in updates.items():
            if key in ("task_id",):
                continue
            if key in json_keys:
                value = json.dumps(value, ensure_ascii=False)
            set_clause.append(f"{key} = ?")
            params.append(value)
        if not set_clause:
            conn.close()
            return False
        set_clause.append("updated_at = ?")
        params.append(datetime.now().isoformat())
        params.append(task_id)
        cursor.execute(f'UPDATE ingest_tasks SET {", ".join(set_clause)} WHERE task_id = ?', params)
        affected = cursor.rowcount
        conn.commit()
        conn.close()
        return affected > 0

    def list_tasks(self, workspace_id: str = None, page: int = 1, page_size: int = 20) -> List[Dict[str, Any]]:
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        if workspace_id:
            cursor.execute(
                'SELECT * FROM ingest_tasks WHERE workspace_id = ? ORDER BY created_at DESC LIMIT ? OFFSET ?',
                (workspace_id, page_size, (page - 1) * page_size),
            )
        else:
            cursor.execute(
                'SELECT * FROM ingest_tasks ORDER BY created_at DESC LIMIT ? OFFSET ?',
                (page_size, (page - 1) * page_size),
            )
        rows = cursor.fetchall()
        conn.close()
        results = []
        for row in rows:
            d = dict(row)
            d["process_steps"] = json.loads(d.get("process_steps") or "[]")
            d["transform_rules"] = json.loads(d.get("transform_rules") or "[]")
            d["extracted_tables"] = json.loads(d.get("extracted_tables") or "[]")
            results.append(d)
        return results
