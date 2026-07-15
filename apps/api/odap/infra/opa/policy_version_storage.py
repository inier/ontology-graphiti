import os
import json
import sqlite3
from typing import Dict, Any, Optional, List
from datetime import datetime


class SQLitePolicyVersionStorage:
    def __init__(self, db_path: str = None):
        self.db_path = db_path or os.path.join(
            os.environ.get("DATA_DIR", os.path.join(os.getcwd(), "data")),
            "policy_versions.db"
        )
        self._init_db()

    def _init_db(self):
        os.makedirs(os.path.dirname(self.db_path), exist_ok=True)
        conn = sqlite3.connect(self.db_path)
        try:
            conn.execute('''CREATE TABLE IF NOT EXISTS policy_versions (
                id TEXT PRIMARY KEY,
                policy_id TEXT NOT NULL,
                rego_text TEXT NOT NULL,
                markdown_text TEXT NOT NULL,
                version INTEGER NOT NULL,
                status TEXT DEFAULT 'active',
                created_at TEXT NOT NULL,
                compiled_at TEXT
            )''')
            conn.execute('''CREATE INDEX IF NOT EXISTS idx_policy_id ON policy_versions(policy_id)''')
            conn.execute('''CREATE INDEX IF NOT EXISTS idx_policy_version ON policy_versions(policy_id, version)''')
            conn.commit()
        finally:
            conn.close()

    def save_version(self, policy_id: str, rego_text: str, markdown_text: str, version: int) -> Dict[str, Any]:
        import uuid
        version_id = str(uuid.uuid4())
        now = datetime.now().isoformat()

        conn = sqlite3.connect(self.db_path)
        try:
            conn.execute(
                "INSERT INTO policy_versions (id, policy_id, rego_text, markdown_text, version, status, created_at, compiled_at) VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
                (version_id, policy_id, rego_text, markdown_text, version, "active", now, now)
            )
            conn.commit()
            return {
                "id": version_id,
                "policy_id": policy_id,
                "version": version,
                "status": "active",
                "created_at": now,
            }
        finally:
            conn.close()

    def get_version(self, policy_id: str, version: int) -> Optional[Dict[str, Any]]:
        conn = sqlite3.connect(self.db_path)
        try:
            cursor = conn.execute(
                "SELECT id, policy_id, rego_text, markdown_text, version, status, created_at, compiled_at FROM policy_versions WHERE policy_id = ? AND version = ?",
                (policy_id, version)
            )
            row = cursor.fetchone()
            if not row:
                return None
            columns = ["id", "policy_id", "rego_text", "markdown_text", "version", "status", "created_at", "compiled_at"]
            return dict(zip(columns, row))
        finally:
            conn.close()

    def list_versions(self, policy_id: str) -> List[Dict[str, Any]]:
        conn = sqlite3.connect(self.db_path)
        try:
            cursor = conn.execute(
                "SELECT id, policy_id, rego_text, markdown_text, version, status, created_at, compiled_at FROM policy_versions WHERE policy_id = ? ORDER BY version DESC",
                (policy_id,)
            )
            columns = ["id", "policy_id", "rego_text", "markdown_text", "version", "status", "created_at", "compiled_at"]
            return [dict(zip(columns, row)) for row in cursor.fetchall()]
        finally:
            conn.close()

    def get_latest_version(self, policy_id: str) -> Optional[Dict[str, Any]]:
        conn = sqlite3.connect(self.db_path)
        try:
            cursor = conn.execute(
                "SELECT id, policy_id, rego_text, markdown_text, version, status, created_at, compiled_at FROM policy_versions WHERE policy_id = ? ORDER BY version DESC LIMIT 1",
                (policy_id,)
            )
            row = cursor.fetchone()
            if not row:
                return None
            columns = ["id", "policy_id", "rego_text", "markdown_text", "version", "status", "created_at", "compiled_at"]
            return dict(zip(columns, row))
        finally:
            conn.close()

    def deactivate_version(self, policy_id: str, version: int) -> bool:
        conn = sqlite3.connect(self.db_path)
        try:
            conn.execute(
                "UPDATE policy_versions SET status = 'inactive' WHERE policy_id = ? AND version = ?",
                (policy_id, version)
            )
            conn.commit()
            return conn.total_changes > 0
        finally:
            conn.close()

    def list_all_policies(self) -> List[Dict[str, Any]]:
        conn = sqlite3.connect(self.db_path)
        try:
            cursor = conn.execute(
                "SELECT policy_id, MAX(version) as version, status, created_at, compiled_at FROM policy_versions WHERE status = 'active' GROUP BY policy_id ORDER BY compiled_at DESC"
            )
            columns = ["policy_id", "version", "status", "created_at", "compiled_at"]
            return [dict(zip(columns, row)) for row in cursor.fetchall()]
        finally:
            conn.close()
