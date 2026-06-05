import os
import json
import sqlite3
from typing import Any, Dict, List, Optional


class SQLiteModelStorage:
    def __init__(self, db_path: str = None):
        self.db_path = db_path or os.path.join(
            os.environ.get("DATA_DIR", os.path.join(os.getcwd(), "data")),
            "ontology_model.db",
        )
        self._init_db()

    def _init_db(self):
        os.makedirs(os.path.dirname(self.db_path), exist_ok=True)
        conn = sqlite3.connect(self.db_path)
        try:
            conn.execute("""
                CREATE TABLE IF NOT EXISTS entity_types (
                    type_id TEXT PRIMARY KEY,
                    name TEXT NOT NULL,
                    display_name TEXT,
                    description TEXT,
                    properties TEXT DEFAULT '[]',
                    primary_key TEXT DEFAULT '[]',
                    links TEXT DEFAULT '[]',
                    actions TEXT DEFAULT '[]',
                    constraints TEXT DEFAULT '[]',
                    classification_level TEXT DEFAULT 'U',
                    metadata TEXT DEFAULT '{}'
                )
            """)
            conn.execute("""
                CREATE TABLE IF NOT EXISTS instances (
                    instance_id TEXT PRIMARY KEY,
                    type_id TEXT NOT NULL,
                    properties TEXT DEFAULT '{}',
                    workspace_id TEXT DEFAULT 'default',
                    created_at TEXT,
                    updated_at TEXT
                )
            """)
            conn.execute("""
                CREATE TABLE IF NOT EXISTS ontology_documents (
                    id TEXT PRIMARY KEY,
                    name TEXT NOT NULL,
                    version TEXT DEFAULT '1.0.0',
                    object_types TEXT DEFAULT '[]',
                    action_types TEXT DEFAULT '[]',
                    relations TEXT DEFAULT '[]',
                    metadata TEXT DEFAULT '{}',
                    created_at TEXT,
                    updated_at TEXT
                )
            """)
            conn.commit()
        finally:
            conn.close()

    def save_entity_type(self, entity_type: Dict[str, Any]) -> Dict[str, Any]:
        conn = sqlite3.connect(self.db_path)
        try:
            conn.execute(
                """INSERT OR REPLACE INTO entity_types
                   (type_id, name, display_name, description, properties, primary_key,
                    links, actions, constraints, classification_level, metadata)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                (
                    entity_type.get("type_id", ""),
                    entity_type.get("name", ""),
                    entity_type.get("display_name"),
                    entity_type.get("description"),
                    json.dumps(entity_type.get("properties", []), ensure_ascii=False),
                    json.dumps(entity_type.get("primary_key", []), ensure_ascii=False),
                    json.dumps(entity_type.get("links", []), ensure_ascii=False),
                    json.dumps(entity_type.get("actions", []), ensure_ascii=False),
                    json.dumps(entity_type.get("constraints", []), ensure_ascii=False),
                    entity_type.get("classification_level", "U"),
                    json.dumps(entity_type.get("metadata", {}), ensure_ascii=False),
                ),
            )
            conn.commit()
            return entity_type
        finally:
            conn.close()

    def get_entity_type(self, type_id: str) -> Optional[Dict[str, Any]]:
        conn = sqlite3.connect(self.db_path)
        try:
            cursor = conn.execute(
                "SELECT * FROM entity_types WHERE type_id = ?", (type_id,)
            )
            row = cursor.fetchone()
            if not row:
                return None
            return self._row_to_entity_type(row)
        finally:
            conn.close()

    def list_entity_types(
        self, filters: Dict[str, Any] = None, page: int = 1, page_size: int = 20
    ) -> List[Dict[str, Any]]:
        conn = sqlite3.connect(self.db_path)
        try:
            query = "SELECT * FROM entity_types"
            params = []
            conditions = []
            if filters:
                if "name" in filters:
                    conditions.append("name LIKE ?")
                    params.append(f"%{filters['name']}%")
                if "classification_level" in filters:
                    conditions.append("classification_level = ?")
                    params.append(filters["classification_level"])
            if conditions:
                query += " WHERE " + " AND ".join(conditions)
            query += " LIMIT ? OFFSET ?"
            params.extend([page_size, (page - 1) * page_size])
            cursor = conn.execute(query, params)
            return [self._row_to_entity_type(row) for row in cursor.fetchall()]
        finally:
            conn.close()

    def delete_entity_type(self, type_id: str) -> bool:
        conn = sqlite3.connect(self.db_path)
        try:
            cursor = conn.execute(
                "DELETE FROM entity_types WHERE type_id = ?", (type_id,)
            )
            conn.commit()
            return cursor.rowcount > 0
        finally:
            conn.close()

    def save_instance(self, instance: Dict[str, Any]) -> Dict[str, Any]:
        conn = sqlite3.connect(self.db_path)
        try:
            conn.execute(
                """INSERT OR REPLACE INTO instances
                   (instance_id, type_id, properties, workspace_id, created_at, updated_at)
                   VALUES (?, ?, ?, ?, ?, ?)""",
                (
                    instance.get("instance_id", ""),
                    instance.get("type_id", ""),
                    json.dumps(instance.get("properties", {}), ensure_ascii=False),
                    instance.get("workspace_id", "default"),
                    instance.get("created_at", ""),
                    instance.get("updated_at", ""),
                ),
            )
            conn.commit()
            return instance
        finally:
            conn.close()

    def get_instance(self, instance_id: str) -> Optional[Dict[str, Any]]:
        conn = sqlite3.connect(self.db_path)
        try:
            cursor = conn.execute(
                "SELECT * FROM instances WHERE instance_id = ?", (instance_id,)
            )
            row = cursor.fetchone()
            if not row:
                return None
            return self._row_to_instance(row)
        finally:
            conn.close()

    def list_instances(
        self,
        type_id: str = None,
        workspace_id: str = None,
        page: int = 1,
        page_size: int = 20,
    ) -> List[Dict[str, Any]]:
        conn = sqlite3.connect(self.db_path)
        try:
            query = "SELECT * FROM instances"
            params = []
            conditions = []
            if type_id:
                conditions.append("type_id = ?")
                params.append(type_id)
            if workspace_id:
                conditions.append("workspace_id = ?")
                params.append(workspace_id)
            if conditions:
                query += " WHERE " + " AND ".join(conditions)
            query += " LIMIT ? OFFSET ?"
            params.extend([page_size, (page - 1) * page_size])
            cursor = conn.execute(query, params)
            return [self._row_to_instance(row) for row in cursor.fetchall()]
        finally:
            conn.close()

    def delete_instance(self, instance_id: str) -> bool:
        conn = sqlite3.connect(self.db_path)
        try:
            cursor = conn.execute(
                "DELETE FROM instances WHERE instance_id = ?", (instance_id,)
            )
            conn.commit()
            return cursor.rowcount > 0
        finally:
            conn.close()

    def batch_import_instances(
        self, instances: List[Dict[str, Any]]
    ) -> Dict[str, Any]:
        success_count = 0
        failed_count = 0
        errors = []
        for instance in instances:
            try:
                self.save_instance(instance)
                success_count += 1
            except Exception as e:
                failed_count += 1
                errors.append(
                    {"instance_id": instance.get("instance_id", ""), "error": str(e)}
                )
        return {
            "success": success_count,
            "failed": failed_count,
            "errors": errors,
        }

    def save_document(self, doc: Dict[str, Any]) -> Dict[str, Any]:
        conn = sqlite3.connect(self.db_path)
        try:
            conn.execute(
                """INSERT OR REPLACE INTO ontology_documents
                   (id, name, version, object_types, action_types, relations, metadata, created_at, updated_at)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                (
                    doc.get("id", ""),
                    doc.get("name", ""),
                    doc.get("version", "1.0.0"),
                    json.dumps(doc.get("object_types", []), ensure_ascii=False),
                    json.dumps(doc.get("action_types", []), ensure_ascii=False),
                    json.dumps(doc.get("relations", []), ensure_ascii=False),
                    json.dumps(doc.get("metadata", {}), ensure_ascii=False),
                    doc.get("created_at", ""),
                    doc.get("updated_at", ""),
                ),
            )
            conn.commit()
            return doc
        finally:
            conn.close()

    def get_document(self, doc_id: str) -> Optional[Dict[str, Any]]:
        conn = sqlite3.connect(self.db_path)
        try:
            cursor = conn.execute(
                "SELECT * FROM ontology_documents WHERE id = ?", (doc_id,)
            )
            row = cursor.fetchone()
            if not row:
                return None
            return self._row_to_document(row)
        finally:
            conn.close()

    def _row_to_entity_type(self, row) -> Dict[str, Any]:
        return {
            "type_id": row[0],
            "name": row[1],
            "display_name": row[2],
            "description": row[3],
            "properties": json.loads(row[4]) if row[4] else [],
            "primary_key": json.loads(row[5]) if row[5] else [],
            "links": json.loads(row[6]) if row[6] else [],
            "actions": json.loads(row[7]) if row[7] else [],
            "constraints": json.loads(row[8]) if row[8] else [],
            "classification_level": row[9],
            "metadata": json.loads(row[10]) if row[10] else {},
        }

    def _row_to_instance(self, row) -> Dict[str, Any]:
        return {
            "instance_id": row[0],
            "type_id": row[1],
            "properties": json.loads(row[2]) if row[2] else {},
            "workspace_id": row[3],
            "created_at": row[4],
            "updated_at": row[5],
        }

    def _row_to_document(self, row) -> Dict[str, Any]:
        return {
            "id": row[0],
            "name": row[1],
            "version": row[2],
            "object_types": json.loads(row[3]) if row[3] else [],
            "action_types": json.loads(row[4]) if row[4] else [],
            "relations": json.loads(row[5]) if row[5] else [],
            "metadata": json.loads(row[6]) if row[6] else {},
            "created_at": row[7],
            "updated_at": row[8],
        }
