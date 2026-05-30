import os
import json
import sqlite3
from datetime import datetime
from typing import Dict, Any, List, Optional


class ServiceCatalogStorage:
    def __init__(self, db_path: str = None):
        self.db_path = db_path or os.path.join(
            os.environ.get("DATA_DIR", os.path.join(os.getcwd(), "data")),
            "ontology_session.db"
        )
        self._init_db()

    def _get_conn(self):
        return sqlite3.connect(self.db_path)

    def _init_db(self):
        os.makedirs(os.path.dirname(self.db_path), exist_ok=True)
        conn = self._get_conn()
        try:
            conn.executescript("""
                CREATE TABLE IF NOT EXISTS service_catalog (
                    catalog_id TEXT PRIMARY KEY,
                    service_id TEXT NOT NULL,
                    service_name TEXT NOT NULL,
                    service_type TEXT NOT NULL,
                    source_ontology_id TEXT,
                    source_object_type TEXT,
                    source_ontology_version TEXT DEFAULT '',
                    current_version INTEGER DEFAULT 1,
                    status TEXT DEFAULT 'active',
                    capabilities TEXT DEFAULT '[]',
                    endpoint_path TEXT DEFAULT '',
                    description TEXT DEFAULT '',
                    registered_at TEXT NOT NULL,
                    last_updated_at TEXT NOT NULL,
                    metadata TEXT DEFAULT '{}'
                );

                CREATE TABLE IF NOT EXISTS service_version_links (
                    link_id TEXT PRIMARY KEY,
                    catalog_id TEXT NOT NULL,
                    ontology_version_id TEXT NOT NULL,
                    service_version INTEGER DEFAULT 1,
                    is_compatible INTEGER DEFAULT 1,
                    notes TEXT DEFAULT '',
                    created_at TEXT NOT NULL,
                    FOREIGN KEY (catalog_id) REFERENCES service_catalog(catalog_id)
                );

                CREATE INDEX IF NOT EXISTS idx_catalog_service ON service_catalog(service_id);
                CREATE INDEX IF NOT EXISTS idx_catalog_ontology ON service_catalog(source_ontology_id);
                CREATE INDEX IF NOT EXISTS idx_catalog_type ON service_catalog(service_type);
                CREATE INDEX IF NOT EXISTS idx_catalog_status ON service_catalog(status);
                CREATE INDEX IF NOT EXISTS idx_version_link_catalog ON service_version_links(catalog_id);
                CREATE INDEX IF NOT EXISTS idx_version_link_ontology ON service_version_links(ontology_version_id);
            """)
            conn.commit()
        finally:
            conn.close()

    def register(self, entry_data: Dict[str, Any]) -> Dict[str, Any]:
        conn = self._get_conn()
        try:
            conn.execute("""
                INSERT OR REPLACE INTO service_catalog
                (catalog_id, service_id, service_name, service_type, source_ontology_id,
                 source_object_type, source_ontology_version, current_version, status,
                 capabilities, endpoint_path, description, registered_at, last_updated_at, metadata)
                VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)
            """, (
                entry_data["catalog_id"], entry_data["service_id"], entry_data["service_name"],
                entry_data["service_type"], entry_data.get("source_ontology_id"),
                entry_data.get("source_object_type"), entry_data.get("source_ontology_version", ""),
                entry_data.get("current_version", 1), entry_data.get("status", "active"),
                json.dumps(entry_data.get("capabilities", []), ensure_ascii=False),
                entry_data.get("endpoint_path", ""),
                entry_data.get("description", ""),
                entry_data.get("registered_at", ""), entry_data.get("last_updated_at", ""),
                json.dumps(entry_data.get("metadata", {}), ensure_ascii=False),
            ))
            conn.commit()
            return entry_data
        finally:
            conn.close()

    def get(self, catalog_id: str) -> Optional[Dict[str, Any]]:
        conn = self._get_conn()
        try:
            row = conn.execute(
                "SELECT * FROM service_catalog WHERE catalog_id = ?", (catalog_id,)
            ).fetchone()
            if not row:
                return None
            return self._row_to_entry(row)
        finally:
            conn.close()

    def get_by_service_id(self, service_id: str) -> Optional[Dict[str, Any]]:
        conn = self._get_conn()
        try:
            row = conn.execute(
                "SELECT * FROM service_catalog WHERE service_id = ?", (service_id,)
            ).fetchone()
            if not row:
                return None
            return self._row_to_entry(row)
        finally:
            conn.close()

    def list_entries(self, service_type: Optional[str] = None,
                     source_ontology_id: Optional[str] = None,
                     status: Optional[str] = None,
                     source_object_type: Optional[str] = None,
                     limit: int = 100) -> List[Dict[str, Any]]:
        conn = self._get_conn()
        try:
            query = "SELECT * FROM service_catalog WHERE 1=1"
            params = []
            if service_type:
                query += " AND service_type = ?"
                params.append(service_type)
            if source_ontology_id:
                query += " AND source_ontology_id = ?"
                params.append(source_ontology_id)
            if status:
                query += " AND status = ?"
                params.append(status)
            if source_object_type:
                query += " AND source_object_type = ?"
                params.append(source_object_type)
            query += " ORDER BY registered_at DESC LIMIT ?"
            params.append(limit)
            rows = conn.execute(query, params).fetchall()
            return [self._row_to_entry(r) for r in rows]
        finally:
            conn.close()

    def update_status(self, catalog_id: str, status: str) -> bool:
        conn = self._get_conn()
        try:
            now = datetime.now().isoformat()
            cursor = conn.execute(
                "UPDATE service_catalog SET status = ?, last_updated_at = ? WHERE catalog_id = ?",
                (status, now, catalog_id),
            )
            conn.commit()
            return cursor.rowcount > 0
        finally:
            conn.close()

    def delete(self, catalog_id: str) -> bool:
        conn = self._get_conn()
        try:
            conn.execute("DELETE FROM service_version_links WHERE catalog_id = ?", (catalog_id,))
            cursor = conn.execute("DELETE FROM service_catalog WHERE catalog_id = ?", (catalog_id,))
            conn.commit()
            return cursor.rowcount > 0
        finally:
            conn.close()

    def add_version_link(self, link_data: Dict[str, Any]) -> Dict[str, Any]:
        conn = self._get_conn()
        try:
            conn.execute("""
                INSERT OR REPLACE INTO service_version_links
                (link_id, catalog_id, ontology_version_id, service_version, is_compatible, notes, created_at)
                VALUES (?,?,?,?,?,?,?)
            """, (
                link_data["link_id"], link_data["catalog_id"], link_data["ontology_version_id"],
                link_data.get("service_version", 1),
                1 if link_data.get("is_compatible", True) else 0,
                link_data.get("notes", ""), link_data.get("created_at", ""),
            ))
            conn.commit()
            return link_data
        finally:
            conn.close()

    def get_version_links(self, catalog_id: str) -> List[Dict[str, Any]]:
        conn = self._get_conn()
        try:
            rows = conn.execute(
                "SELECT * FROM service_version_links WHERE catalog_id = ?", (catalog_id,)
            ).fetchall()
            return [self._row_to_link(r) for r in rows]
        finally:
            conn.close()

    def get_services_by_ontology_version(self, ontology_version_id: str) -> List[Dict[str, Any]]:
        conn = self._get_conn()
        try:
            rows = conn.execute("""
                SELECT sc.* FROM service_catalog sc
                JOIN service_version_links svl ON sc.catalog_id = svl.catalog_id
                WHERE svl.ontology_version_id = ?
            """, (ontology_version_id,)).fetchall()
            return [self._row_to_entry(r) for r in rows]
        finally:
            conn.close()

    def _row_to_entry(self, row) -> Dict[str, Any]:
        return {
            "catalog_id": row[0], "service_id": row[1], "service_name": row[2],
            "service_type": row[3], "source_ontology_id": row[4],
            "source_object_type": row[5], "source_ontology_version": row[6],
            "current_version": row[7], "status": row[8],
            "capabilities": json.loads(row[9]) if row[9] else [],
            "endpoint_path": row[10], "description": row[11],
            "registered_at": row[12], "last_updated_at": row[13],
            "metadata": json.loads(row[14]) if row[14] else {},
        }

    def _row_to_link(self, row) -> Dict[str, Any]:
        return {
            "link_id": row[0], "catalog_id": row[1],
            "ontology_version_id": row[2], "service_version": row[3],
            "is_compatible": bool(row[4]), "notes": row[5], "created_at": row[6],
        }
