import os
import json
import sqlite3
from typing import List, Dict, Any, Optional


class SQLiteSandboxStorage:
    def __init__(self, db_path: str = None):
        self.db_path = db_path or os.path.join(
            os.environ.get("DATA_DIR", os.path.join(os.getcwd(), "data")),
            "simulation_sandbox.db"
        )
        self._init_db()

    def _init_db(self):
        conn = sqlite3.connect(self.db_path)
        try:
            conn.execute("""
                CREATE TABLE IF NOT EXISTS sandboxes (
                    sandbox_id TEXT PRIMARY KEY,
                    name TEXT DEFAULT '',
                    description TEXT DEFAULT '',
                    status TEXT NOT NULL,
                    config TEXT DEFAULT '{}',
                    isolation_level TEXT DEFAULT 'in_process',
                    created_at TEXT,
                    started_at TEXT,
                    completed_at TEXT
                )
            """)
            conn.execute("""
                CREATE TABLE IF NOT EXISTS sandbox_results (
                    sandbox_id TEXT PRIMARY KEY,
                    risk_assessment TEXT DEFAULT '{}',
                    metric_changes TEXT DEFAULT '[]',
                    recommendations TEXT DEFAULT '[]',
                    summary TEXT DEFAULT '',
                    created_at TEXT,
                    FOREIGN KEY (sandbox_id) REFERENCES sandboxes(sandbox_id)
                )
            """)
            conn.commit()
        finally:
            conn.close()

    def save_sandbox(self, sandbox: Dict[str, Any]) -> Dict[str, Any]:
        conn = sqlite3.connect(self.db_path)
        try:
            config = sandbox.get("config", {})
            if isinstance(config, str):
                try:
                    config = json.loads(config)
                except (json.JSONDecodeError, TypeError):
                    config = {}
            conn.execute("""
                INSERT OR REPLACE INTO sandboxes
                (sandbox_id, name, description, status, config,
                 isolation_level, created_at, started_at, completed_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                sandbox.get("sandbox_id", ""),
                sandbox.get("name", ""),
                sandbox.get("description", ""),
                sandbox.get("status", "created"),
                json.dumps(config, ensure_ascii=False),
                sandbox.get("isolation_level", "in_process"),
                sandbox.get("created_at", ""),
                sandbox.get("started_at"),
                sandbox.get("completed_at"),
            ))
            conn.commit()
        finally:
            conn.close()
        return sandbox

    def get_sandbox(self, sandbox_id: str) -> Optional[Dict[str, Any]]:
        conn = sqlite3.connect(self.db_path)
        try:
            conn.row_factory = sqlite3.Row
            cursor = conn.execute(
                "SELECT * FROM sandboxes WHERE sandbox_id = ?",
                (sandbox_id,)
            )
            row = cursor.fetchone()
            if not row:
                return None
            return self._sandbox_row_to_dict(row)
        finally:
            conn.close()

    def list_sandboxes(self) -> List[Dict[str, Any]]:
        conn = sqlite3.connect(self.db_path)
        try:
            conn.row_factory = sqlite3.Row
            cursor = conn.execute(
                "SELECT * FROM sandboxes ORDER BY created_at DESC"
            )
            rows = cursor.fetchall()
            return [self._sandbox_row_to_dict(row) for row in rows]
        finally:
            conn.close()

    def delete_sandbox(self, sandbox_id: str) -> bool:
        conn = sqlite3.connect(self.db_path)
        try:
            conn.execute(
                "DELETE FROM sandbox_results WHERE sandbox_id = ?",
                (sandbox_id,)
            )
            cursor = conn.execute(
                "DELETE FROM sandboxes WHERE sandbox_id = ?",
                (sandbox_id,)
            )
            conn.commit()
            return cursor.rowcount > 0
        finally:
            conn.close()

    def save_result(self, sandbox_id: str, result: Dict[str, Any]) -> Dict[str, Any]:
        from datetime import datetime, timezone
        conn = sqlite3.connect(self.db_path)
        try:
            risk_assessment = result.get("risk_assessment", {})
            if not isinstance(risk_assessment, dict):
                risk_assessment = {}
            metric_changes = result.get("metric_changes", [])
            if not isinstance(metric_changes, list):
                metric_changes = []
            recommendations = result.get("recommendations", [])
            if not isinstance(recommendations, list):
                recommendations = []
            summary = result.get("summary", result.get("recommendation", ""))
            if not isinstance(summary, str):
                summary = json.dumps(summary, ensure_ascii=False)
            created_at = result.get("transaction_time", datetime.now(timezone.utc).isoformat())
            conn.execute("""
                INSERT OR REPLACE INTO sandbox_results
                (sandbox_id, risk_assessment, metric_changes, recommendations,
                 summary, created_at)
                VALUES (?, ?, ?, ?, ?, ?)
            """, (
                sandbox_id,
                json.dumps(risk_assessment, ensure_ascii=False),
                json.dumps(metric_changes, ensure_ascii=False),
                json.dumps(recommendations, ensure_ascii=False),
                summary,
                created_at,
            ))
            conn.commit()
        finally:
            conn.close()
        return result

    def get_result(self, sandbox_id: str) -> Optional[Dict[str, Any]]:
        conn = sqlite3.connect(self.db_path)
        try:
            conn.row_factory = sqlite3.Row
            cursor = conn.execute(
                "SELECT * FROM sandbox_results WHERE sandbox_id = ?",
                (sandbox_id,)
            )
            row = cursor.fetchone()
            if not row:
                return None
            return self._result_row_to_dict(row)
        finally:
            conn.close()

    def _sandbox_row_to_dict(self, row) -> Dict[str, Any]:
        d = dict(row)
        if "config" in d and isinstance(d["config"], str):
            try:
                d["config"] = json.loads(d["config"])
            except (json.JSONDecodeError, TypeError):
                d["config"] = {}
        return d

    def _result_row_to_dict(self, row) -> Dict[str, Any]:
        d = dict(row)
        for key in ("risk_assessment", "metric_changes", "recommendations"):
            if key in d and isinstance(d[key], str):
                try:
                    d[key] = json.loads(d[key])
                except (json.JSONDecodeError, TypeError):
                    d[key] = {} if key == "risk_assessment" else []
        return d
