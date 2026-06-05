import os
import json
import sqlite3
import logging
from typing import Dict, Any, List, Optional
from datetime import datetime

logger = logging.getLogger("servitization_storage")


class SQLiteServitizationStorage:
    def __init__(self, db_path: str = None):
        self.db_path = db_path or os.path.join(
            os.environ.get("DATA_DIR", os.path.join(os.getcwd(), "data")), "ontology_session.db")
        self._init_db()

    def _get_conn(self):
        return sqlite3.connect(self.db_path)

    def _init_db(self):
        os.makedirs(os.path.dirname(self.db_path), exist_ok=True)
        conn = self._get_conn()
        try:
            conn.executescript("""
                CREATE TABLE IF NOT EXISTS skill_templates (
                    template_id TEXT PRIMARY KEY,
                    name TEXT NOT NULL,
                    description TEXT DEFAULT '',
                    service_type TEXT DEFAULT 'skill',
                    object_type TEXT DEFAULT '',
                    function_mappings TEXT DEFAULT '[]',
                    parameter_schema TEXT DEFAULT '{}',
                    output_schema TEXT DEFAULT '{}',
                    code_template TEXT DEFAULT '',
                    created_at TEXT DEFAULT ''
                );

                CREATE TABLE IF NOT EXISTS generated_services (
                    service_id TEXT PRIMARY KEY,
                    name TEXT NOT NULL,
                    description TEXT DEFAULT '',
                    service_type TEXT DEFAULT 'skill',
                    source_ontology_id TEXT DEFAULT '',
                    source_object_type TEXT DEFAULT '',
                    source_function_ids TEXT DEFAULT '[]',
                    template_id TEXT,
                    code TEXT DEFAULT '',
                    parameter_schema TEXT DEFAULT '{}',
                    output_schema TEXT DEFAULT '{}',
                    endpoint_path TEXT,
                    status TEXT DEFAULT 'pending',
                    version INTEGER DEFAULT 1,
                    created_at TEXT DEFAULT '',
                    updated_at TEXT DEFAULT ''
                );

                CREATE TABLE IF NOT EXISTS service_deployments (
                    deployment_id TEXT PRIMARY KEY,
                    service_id TEXT NOT NULL,
                    endpoint_url TEXT DEFAULT '',
                    deployed_at TEXT DEFAULT '',
                    is_active INTEGER DEFAULT 1,
                    health_status TEXT DEFAULT 'unknown',
                    last_health_check TEXT
                );

                CREATE INDEX IF NOT EXISTS idx_templates_service_type ON skill_templates(service_type);
                CREATE INDEX IF NOT EXISTS idx_templates_object_type ON skill_templates(object_type);
                CREATE INDEX IF NOT EXISTS idx_services_status ON generated_services(status);
                CREATE INDEX IF NOT EXISTS idx_services_service_type ON generated_services(service_type);
                CREATE INDEX IF NOT EXISTS idx_services_source_ontology ON generated_services(source_ontology_id);
                CREATE INDEX IF NOT EXISTS idx_deployments_service_id ON service_deployments(service_id);
                CREATE INDEX IF NOT EXISTS idx_deployments_active ON service_deployments(is_active);
            """)
            conn.commit()
        finally:
            conn.close()

    def save_template(self, template: Dict[str, Any]) -> Dict[str, Any]:
        conn = self._get_conn()
        try:
            conn.execute("""
                INSERT OR REPLACE INTO skill_templates
                (template_id, name, description, service_type, object_type,
                 function_mappings, parameter_schema, output_schema, code_template, created_at)
                VALUES (?,?,?,?,?,?,?,?,?,?)
            """, (
                template["template_id"], template.get("name", ""),
                template.get("description", ""), template.get("service_type", "skill"),
                template.get("object_type", ""),
                json.dumps(template.get("function_mappings", []), ensure_ascii=False),
                json.dumps(template.get("parameter_schema", {}), ensure_ascii=False),
                json.dumps(template.get("output_schema", {}), ensure_ascii=False),
                template.get("code_template", ""), template.get("created_at", ""),
            ))
            conn.commit()
            return template
        finally:
            conn.close()

    def get_template(self, template_id: str) -> Optional[Dict[str, Any]]:
        conn = self._get_conn()
        try:
            row = conn.execute("SELECT * FROM skill_templates WHERE template_id = ?", (template_id,)).fetchone()
            if not row:
                return None
            return self._row_to_template(row)
        finally:
            conn.close()

    def list_templates(self, service_type: Optional[str] = None) -> List[Dict[str, Any]]:
        conn = self._get_conn()
        try:
            if service_type:
                rows = conn.execute("SELECT * FROM skill_templates WHERE service_type = ? ORDER BY created_at DESC", (service_type,)).fetchall()
            else:
                rows = conn.execute("SELECT * FROM skill_templates ORDER BY created_at DESC").fetchall()
            return [self._row_to_template(r) for r in rows]
        finally:
            conn.close()

    def delete_template(self, template_id: str) -> bool:
        conn = self._get_conn()
        try:
            cursor = conn.execute("DELETE FROM skill_templates WHERE template_id = ?", (template_id,))
            conn.commit()
            return cursor.rowcount > 0
        finally:
            conn.close()

    def _row_to_template(self, row) -> Dict[str, Any]:
        return {
            "template_id": row[0], "name": row[1], "description": row[2],
            "service_type": row[3], "object_type": row[4],
            "function_mappings": json.loads(row[5]) if row[5] else [],
            "parameter_schema": json.loads(row[6]) if row[6] else {},
            "output_schema": json.loads(row[7]) if row[7] else {},
            "code_template": row[8], "created_at": row[9],
        }

    def save_service(self, service: Dict[str, Any]) -> Dict[str, Any]:
        conn = self._get_conn()
        try:
            conn.execute("""
                INSERT OR REPLACE INTO generated_services
                (service_id, name, description, service_type, source_ontology_id,
                 source_object_type, source_function_ids, template_id, code,
                 parameter_schema, output_schema, endpoint_path, status,
                 version, created_at, updated_at)
                VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)
            """, (
                service["service_id"], service.get("name", ""),
                service.get("description", ""), service.get("service_type", "skill"),
                service.get("source_ontology_id", ""), service.get("source_object_type", ""),
                json.dumps(service.get("source_function_ids", []), ensure_ascii=False),
                service.get("template_id"),
                service.get("code", ""),
                json.dumps(service.get("parameter_schema", {}), ensure_ascii=False),
                json.dumps(service.get("output_schema", {}), ensure_ascii=False),
                service.get("endpoint_path"),
                service.get("status", "pending"), service.get("version", 1),
                service.get("created_at", ""), service.get("updated_at", ""),
            ))
            conn.commit()
            return service
        finally:
            conn.close()

    def get_service(self, service_id: str) -> Optional[Dict[str, Any]]:
        conn = self._get_conn()
        try:
            row = conn.execute("SELECT * FROM generated_services WHERE service_id = ?", (service_id,)).fetchone()
            if not row:
                return None
            return self._row_to_service(row)
        finally:
            conn.close()

    def list_services(self, service_type: Optional[str] = None, status: Optional[str] = None) -> List[Dict[str, Any]]:
        conn = self._get_conn()
        try:
            sql = "SELECT * FROM generated_services WHERE 1=1"
            params = []
            if service_type:
                sql += " AND service_type = ?"
                params.append(service_type)
            if status:
                sql += " AND status = ?"
                params.append(status)
            sql += " ORDER BY created_at DESC"
            rows = conn.execute(sql, params).fetchall()
            return [self._row_to_service(r) for r in rows]
        finally:
            conn.close()

    def update_service_status(self, service_id: str, status: str) -> bool:
        conn = self._get_conn()
        try:
            now = datetime.now().isoformat()
            cursor = conn.execute(
                "UPDATE generated_services SET status = ?, updated_at = ? WHERE service_id = ?",
                (status, now, service_id))
            conn.commit()
            return cursor.rowcount > 0
        finally:
            conn.close()

    def delete_service(self, service_id: str) -> bool:
        conn = self._get_conn()
        try:
            cursor = conn.execute("DELETE FROM generated_services WHERE service_id = ?", (service_id,))
            conn.commit()
            return cursor.rowcount > 0
        finally:
            conn.close()

    def _row_to_service(self, row) -> Dict[str, Any]:
        return {
            "service_id": row[0], "name": row[1], "description": row[2],
            "service_type": row[3], "source_ontology_id": row[4],
            "source_object_type": row[5],
            "source_function_ids": json.loads(row[6]) if row[6] else [],
            "template_id": row[7], "code": row[8],
            "parameter_schema": json.loads(row[9]) if row[9] else {},
            "output_schema": json.loads(row[10]) if row[10] else {},
            "endpoint_path": row[11], "status": row[12],
            "version": row[13], "created_at": row[14], "updated_at": row[15],
        }

    def save_deployment(self, deployment: Dict[str, Any]) -> Dict[str, Any]:
        conn = self._get_conn()
        try:
            conn.execute("""
                INSERT OR REPLACE INTO service_deployments
                (deployment_id, service_id, endpoint_url, deployed_at,
                 is_active, health_status, last_health_check)
                VALUES (?,?,?,?,?,?,?)
            """, (
                deployment["deployment_id"], deployment.get("service_id", ""),
                deployment.get("endpoint_url", ""), deployment.get("deployed_at", ""),
                1 if deployment.get("is_active", True) else 0,
                deployment.get("health_status", "unknown"),
                deployment.get("last_health_check"),
            ))
            conn.commit()
            return deployment
        finally:
            conn.close()

    def get_deployment(self, deployment_id: str) -> Optional[Dict[str, Any]]:
        conn = self._get_conn()
        try:
            row = conn.execute("SELECT * FROM service_deployments WHERE deployment_id = ?", (deployment_id,)).fetchone()
            if not row:
                return None
            return self._row_to_deployment(row)
        finally:
            conn.close()

    def get_deployment_by_service(self, service_id: str) -> Optional[Dict[str, Any]]:
        conn = self._get_conn()
        try:
            row = conn.execute("SELECT * FROM service_deployments WHERE service_id = ? AND is_active = 1", (service_id,)).fetchone()
            if not row:
                return None
            return self._row_to_deployment(row)
        finally:
            conn.close()

    def list_deployments(self, service_id: Optional[str] = None) -> List[Dict[str, Any]]:
        conn = self._get_conn()
        try:
            if service_id:
                rows = conn.execute("SELECT * FROM service_deployments WHERE service_id = ? ORDER BY deployed_at DESC", (service_id,)).fetchall()
            else:
                rows = conn.execute("SELECT * FROM service_deployments ORDER BY deployed_at DESC").fetchall()
            return [self._row_to_deployment(r) for r in rows]
        finally:
            conn.close()

    def update_deployment_status(self, deployment_id: str, is_active: bool, health_status: Optional[str] = None) -> bool:
        conn = self._get_conn()
        try:
            now = datetime.now().isoformat()
            if health_status:
                cursor = conn.execute(
                    "UPDATE service_deployments SET is_active = ?, health_status = ?, last_health_check = ? WHERE deployment_id = ?",
                    (1 if is_active else 0, health_status, now, deployment_id))
            else:
                cursor = conn.execute(
                    "UPDATE service_deployments SET is_active = ?, last_health_check = ? WHERE deployment_id = ?",
                    (1 if is_active else 0, now, deployment_id))
            conn.commit()
            return cursor.rowcount > 0
        finally:
            conn.close()

    def delete_deployment(self, deployment_id: str) -> bool:
        conn = self._get_conn()
        try:
            cursor = conn.execute("DELETE FROM service_deployments WHERE deployment_id = ?", (deployment_id,))
            conn.commit()
            return cursor.rowcount > 0
        finally:
            conn.close()

    def _row_to_deployment(self, row) -> Dict[str, Any]:
        return {
            "deployment_id": row[0], "service_id": row[1],
            "endpoint_url": row[2], "deployed_at": row[3],
            "is_active": bool(row[4]), "health_status": row[5],
            "last_health_check": row[6],
        }
