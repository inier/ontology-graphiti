import os
import json
import sqlite3
import logging
from typing import List, Dict, Any, Optional

logger = logging.getLogger(__name__)


def _sb_storage_audit(action: str, *, result_status: str = "success",
                      result_message: str = "", resource: str = None,
                      details: Dict[str, Any] = None) -> None:
    """Sandbox 存储层审计：失败仅 warning，不阻断业务"""
    try:
        from odap.infra.security.audit_helper import storage_audit
        storage_audit(
            action=action,
            result_status=result_status,
            result_message=result_message,
            resource=resource,
            details=details or {},
            service="simulation_sandbox",
        )
    except Exception as e:
        logger.warning(f"Audit write failed (sandbox storage) action={action}: {e}")


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
        sid = sandbox.get("sandbox_id", "")
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
                sid,
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
            _sb_storage_audit(
                "sandbox_storage_save",
                result_status="success",
                resource=sid,
                details={
                    "sandbox_id": sid,
                    "status": sandbox.get("status", "created"),
                    "scenario_id": config.get("scenario_id", "") if isinstance(config, dict) else "",
                },
            )
        except Exception as e:
            _sb_storage_audit(
                "sandbox_storage_save",
                result_status="failure",
                resource=sid,
                result_message=str(e),
                details={"sandbox_id": sid},
            )
            raise
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
            deleted = cursor.rowcount > 0
            _sb_storage_audit(
                "sandbox_storage_delete",
                result_status="success" if deleted else "failure",
                resource=sandbox_id,
                result_message="" if deleted else "Sandbox not found in storage",
                details={"sandbox_id": sandbox_id},
            )
            return deleted
        except Exception as e:
            _sb_storage_audit(
                "sandbox_storage_delete",
                result_status="failure",
                resource=sandbox_id,
                result_message=str(e),
                details={"sandbox_id": sandbox_id},
            )
            raise
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
            _sb_storage_audit(
                "sandbox_storage_save_result",
                result_status="success",
                resource=sandbox_id,
                details={
                    "sandbox_id": sandbox_id,
                    "metric_changes_count": len(metric_changes),
                    "recommendations_count": len(recommendations),
                },
            )
        except Exception as e:
            _sb_storage_audit(
                "sandbox_storage_save_result",
                result_status="failure",
                resource=sandbox_id,
                result_message=str(e),
                details={"sandbox_id": sandbox_id},
            )
            raise
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
