import os
import json
import sqlite3
from typing import Any, Dict, List, Optional


class SQLiteEngineStorage:
    def __init__(self, db_path: str = None):
        self.db_path = db_path or os.path.join(
            os.environ.get("DATA_DIR", os.path.join(os.getcwd(), "data")),
            "ontology_engine.db",
        )
        self._init_db()

    def _init_db(self):
        os.makedirs(os.path.dirname(self.db_path), exist_ok=True)
        conn = sqlite3.connect(self.db_path)
        try:
            conn.execute("""
                CREATE TABLE IF NOT EXISTS versions (
                    version_id TEXT PRIMARY KEY,
                    ontology_id TEXT NOT NULL,
                    version_number TEXT DEFAULT '1.0.0',
                    changelog TEXT DEFAULT '',
                    valid_time TEXT DEFAULT '',
                    transaction_time TEXT DEFAULT '',
                    status TEXT DEFAULT 'draft',
                    snapshot TEXT DEFAULT '{}'
                )
            """)
            conn.execute("""
                CREATE INDEX IF NOT EXISTS idx_versions_ontology_id ON versions(ontology_id)
            """)
            conn.execute("""
                CREATE TABLE IF NOT EXISTS audit_records (
                    audit_id TEXT PRIMARY KEY,
                    entity_type_id TEXT DEFAULT '',
                    source TEXT DEFAULT '',
                    process_steps TEXT DEFAULT '[]',
                    transform_rules TEXT DEFAULT '[]',
                    result TEXT DEFAULT '',
                    timestamp TEXT DEFAULT ''
                )
            """)
            conn.execute("""
                CREATE TABLE IF NOT EXISTS ingest_audit_records (
                    audit_id TEXT PRIMARY KEY,
                    entity_type_id TEXT DEFAULT '',
                    source TEXT DEFAULT '',
                    source_type TEXT DEFAULT '',
                    process_steps TEXT DEFAULT '[]',
                    transform_rules TEXT DEFAULT '[]',
                    result TEXT DEFAULT '',
                    timestamp TEXT DEFAULT ''
                )
            """)
            conn.execute("""
                CREATE INDEX IF NOT EXISTS idx_ingest_audit_source_type ON ingest_audit_records(source_type)
            """)
            conn.execute("""
                CREATE INDEX IF NOT EXISTS idx_ingest_audit_source ON ingest_audit_records(source)
            """)
            conn.execute("""
                CREATE INDEX IF NOT EXISTS idx_ingest_audit_entity_type ON ingest_audit_records(entity_type_id)
            """)
            conn.commit()
        finally:
            conn.close()

    def save_version(self, version: Dict[str, Any]) -> Dict[str, Any]:
        conn = sqlite3.connect(self.db_path)
        try:
            conn.execute(
                """INSERT OR REPLACE INTO versions
                   (version_id, ontology_id, version_number, changelog, valid_time, transaction_time, status, snapshot)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
                (
                    version.get("version_id", ""),
                    version.get("ontology_id", ""),
                    version.get("version_number", "1.0.0"),
                    version.get("changelog", ""),
                    version.get("valid_time", ""),
                    version.get("transaction_time", ""),
                    version.get("status", "draft"),
                    json.dumps(version.get("snapshot", {}), ensure_ascii=False),
                ),
            )
            conn.commit()
            return version
        finally:
            conn.close()

    def get_version(self, version_id: str) -> Optional[Dict[str, Any]]:
        conn = sqlite3.connect(self.db_path)
        try:
            cursor = conn.execute(
                "SELECT * FROM versions WHERE version_id = ?", (version_id,)
            )
            row = cursor.fetchone()
            if not row:
                return None
            return self._row_to_version(row)
        finally:
            conn.close()

    def list_versions(self, ontology_id: str, page: int = 1, page_size: int = 20) -> List[Dict[str, Any]]:
        conn = sqlite3.connect(self.db_path)
        try:
            cursor = conn.execute(
                "SELECT * FROM versions WHERE ontology_id = ? ORDER BY transaction_time DESC LIMIT ? OFFSET ?",
                (ontology_id, page_size, (page - 1) * page_size),
            )
            return [self._row_to_version(row) for row in cursor.fetchall()]
        finally:
            conn.close()

    def get_version_at_time(self, ontology_id: str, timestamp: str) -> Optional[Dict[str, Any]]:
        conn = sqlite3.connect(self.db_path)
        try:
            cursor = conn.execute(
                "SELECT * FROM versions WHERE ontology_id = ? AND valid_time <= ? AND status = 'active' ORDER BY valid_time DESC LIMIT 1",
                (ontology_id, timestamp),
            )
            row = cursor.fetchone()
            if not row:
                return None
            return self._row_to_version(row)
        finally:
            conn.close()

    def save_audit(self, audit: Dict[str, Any]) -> Dict[str, Any]:
        conn = sqlite3.connect(self.db_path)
        try:
            conn.execute(
                """INSERT OR REPLACE INTO audit_records
                   (audit_id, entity_type_id, source, process_steps, transform_rules, result, timestamp)
                   VALUES (?, ?, ?, ?, ?, ?, ?)""",
                (
                    audit.get("audit_id", ""),
                    audit.get("entity_type_id", ""),
                    audit.get("source", ""),
                    json.dumps(audit.get("process_steps", []), ensure_ascii=False),
                    json.dumps(audit.get("transform_rules", []), ensure_ascii=False),
                    audit.get("result", ""),
                    audit.get("timestamp", ""),
                ),
            )
            conn.commit()
            return audit
        finally:
            conn.close()

    def get_audit(self, audit_id: str) -> Optional[Dict[str, Any]]:
        conn = sqlite3.connect(self.db_path)
        try:
            cursor = conn.execute(
                "SELECT * FROM audit_records WHERE audit_id = ?", (audit_id,)
            )
            row = cursor.fetchone()
            if not row:
                return None
            return self._row_to_audit(row)
        finally:
            conn.close()

    def list_audits(self, entity_type_id: str = None, page: int = 1, page_size: int = 20) -> List[Dict[str, Any]]:
        conn = sqlite3.connect(self.db_path)
        try:
            if entity_type_id:
                cursor = conn.execute(
                    "SELECT * FROM audit_records WHERE entity_type_id = ? ORDER BY timestamp DESC LIMIT ? OFFSET ?",
                    (entity_type_id, page_size, (page - 1) * page_size),
                )
            else:
                cursor = conn.execute(
                    "SELECT * FROM audit_records ORDER BY timestamp DESC LIMIT ? OFFSET ?",
                    (page_size, (page - 1) * page_size),
                )
            return [self._row_to_audit(row) for row in cursor.fetchall()]
        finally:
            conn.close()

    def _row_to_version(self, row) -> Dict[str, Any]:
        return {
            "version_id": row[0],
            "ontology_id": row[1],
            "version_number": row[2],
            "changelog": row[3],
            "valid_time": row[4],
            "transaction_time": row[5],
            "status": row[6],
            "snapshot": json.loads(row[7]) if row[7] else {},
        }

    def _row_to_audit(self, row) -> Dict[str, Any]:
        return {
            "audit_id": row[0],
            "entity_type_id": row[1],
            "source": row[2],
            "process_steps": json.loads(row[3]) if row[3] else [],
            "transform_rules": json.loads(row[4]) if row[4] else [],
            "result": row[5],
            "timestamp": row[6],
        }

    def save_ingest_audit(self, audit: Dict[str, Any]) -> Dict[str, Any]:
        conn = sqlite3.connect(self.db_path)
        try:
            conn.execute(
                """INSERT OR REPLACE INTO ingest_audit_records
                   (audit_id, entity_type_id, source, source_type, process_steps, transform_rules, result, timestamp)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
                (
                    audit.get("audit_id", ""),
                    audit.get("entity_type_id", ""),
                    audit.get("source", ""),
                    audit.get("source_type", ""),
                    json.dumps(audit.get("process_steps", []), ensure_ascii=False),
                    json.dumps(audit.get("transform_rules", []), ensure_ascii=False),
                    audit.get("result", ""),
                    audit.get("timestamp", ""),
                ),
            )
            conn.commit()
            return audit
        finally:
            conn.close()

    def get_ingest_audit(self, audit_id: str) -> Optional[Dict[str, Any]]:
        conn = sqlite3.connect(self.db_path)
        try:
            cursor = conn.execute(
                "SELECT * FROM ingest_audit_records WHERE audit_id = ?", (audit_id,)
            )
            row = cursor.fetchone()
            if not row:
                return None
            return self._row_to_ingest_audit(row)
        finally:
            conn.close()

    def list_ingest_audits(self, entity_type_id: str = None, source: str = None, source_type: str = None, page: int = 1, page_size: int = 20) -> List[Dict[str, Any]]:
        conn = sqlite3.connect(self.db_path)
        try:
            conditions = []
            params = []
            if entity_type_id:
                conditions.append("entity_type_id = ?")
                params.append(entity_type_id)
            if source:
                conditions.append("source = ?")
                params.append(source)
            if source_type:
                conditions.append("source_type = ?")
                params.append(source_type)

            where_clause = ""
            if conditions:
                where_clause = " WHERE " + " AND ".join(conditions)

            query = f"SELECT * FROM ingest_audit_records{where_clause} ORDER BY timestamp DESC LIMIT ? OFFSET ?"
            params.extend([page_size, (page - 1) * page_size])
            cursor = conn.execute(query, params)
            return [self._row_to_ingest_audit(row) for row in cursor.fetchall()]
        finally:
            conn.close()

    def _row_to_ingest_audit(self, row) -> Dict[str, Any]:
        return {
            "audit_id": row[0],
            "entity_type_id": row[1],
            "source": row[2],
            "source_type": row[3] if len(row) > 3 else "",
            "process_steps": json.loads(row[4]) if len(row) > 4 and row[4] else [],
            "transform_rules": json.loads(row[5]) if len(row) > 5 and row[5] else [],
            "result": row[6] if len(row) > 6 else "",
            "timestamp": row[7] if len(row) > 7 else "",
        }
