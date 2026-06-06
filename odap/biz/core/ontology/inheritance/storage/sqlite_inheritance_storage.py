"""
SQLiteInheritanceStorage (T369)

表:
- inheritance_edges: (id, child_type_id, parent_type_id, depth, discriminator, created_at, UNIQUE(child, parent))
- mixins: (id, name, description, properties, target_type_ids, created_at)

对齐 AGENTS.md 规则 8：每次 connect/close、无连接池、JSON 存 TEXT。
"""
from __future__ import annotations

import json
import os
import sqlite3
from datetime import datetime
from typing import Any, Dict, List, Optional


class SQLiteInheritanceStorage:
    def __init__(self, db_path: str = None):
        self.db_path = db_path or os.path.join(
            os.environ.get("DATA_DIR", os.path.join(os.getcwd(), "data")),
            "ontology_inheritance.db",
        )
        self._init_db()

    def _init_db(self) -> None:
        os.makedirs(os.path.dirname(self.db_path), exist_ok=True)
        conn = sqlite3.connect(self.db_path)
        try:
            conn.execute("""
                CREATE TABLE IF NOT EXISTS inheritance_edges (
                    id TEXT PRIMARY KEY,
                    child_type_id TEXT NOT NULL,
                    parent_type_id TEXT NOT NULL,
                    depth INTEGER DEFAULT 1,
                    discriminator TEXT DEFAULT '{}',
                    created_at TEXT,
                    UNIQUE(child_type_id, parent_type_id)
                )
            """)
            conn.execute("""
                CREATE TABLE IF NOT EXISTS mixins (
                    id TEXT PRIMARY KEY,
                    name TEXT NOT NULL,
                    description TEXT DEFAULT '',
                    properties TEXT DEFAULT '[]',
                    target_type_ids TEXT DEFAULT '[]',
                    created_at TEXT
                )
            """)
            conn.commit()
        finally:
            conn.close()

    # ============== edges ==============

    def save_edge(self, edge: Dict[str, Any]) -> Dict[str, Any]:
        created = edge.get("created_at")
        if isinstance(created, datetime):
            created = created.isoformat()
        conn = sqlite3.connect(self.db_path)
        try:
            conn.execute(
                """INSERT OR REPLACE INTO inheritance_edges
                   (id, child_type_id, parent_type_id, depth, discriminator, created_at)
                   VALUES (?, ?, ?, ?, ?, ?)""",
                (
                    edge.get("id", ""),
                    edge.get("child_type_id", ""),
                    edge.get("parent_type_id", ""),
                    int(edge.get("depth", 1)),
                    json.dumps(edge.get("discriminator", {}), ensure_ascii=False),
                    created or datetime.now().isoformat(),
                ),
            )
            conn.commit()
            return edge
        finally:
            conn.close()

    def delete_edge(self, edge_id: str) -> bool:
        conn = sqlite3.connect(self.db_path)
        try:
            cursor = conn.execute(
                "DELETE FROM inheritance_edges WHERE id = ?", (edge_id,)
            )
            conn.commit()
            return cursor.rowcount > 0
        finally:
            conn.close()

    def delete_edge_by_pair(self, child_id: str, parent_id: str) -> bool:
        conn = sqlite3.connect(self.db_path)
        try:
            cursor = conn.execute(
                "DELETE FROM inheritance_edges WHERE child_type_id = ? AND parent_type_id = ?",
                (child_id, parent_id),
            )
            conn.commit()
            return cursor.rowcount > 0
        finally:
            conn.close()

    def get_edge(self, edge_id: str) -> Optional[Dict[str, Any]]:
        conn = sqlite3.connect(self.db_path)
        try:
            cursor = conn.execute(
                "SELECT * FROM inheritance_edges WHERE id = ?", (edge_id,)
            )
            row = cursor.fetchone()
            if not row:
                return None
            return self._row_to_edge(row)
        finally:
            conn.close()

    def list_edges(
        self, child_id: str = None, parent_id: str = None
    ) -> List[Dict[str, Any]]:
        conn = sqlite3.connect(self.db_path)
        try:
            query = "SELECT * FROM inheritance_edges"
            params: List[Any] = []
            conds: List[str] = []
            if child_id:
                conds.append("child_type_id = ?")
                params.append(child_id)
            if parent_id:
                conds.append("parent_type_id = ?")
                params.append(parent_id)
            if conds:
                query += " WHERE " + " AND ".join(conds)
            cursor = conn.execute(query, params)
            return [self._row_to_edge(r) for r in cursor.fetchall()]
        finally:
            conn.close()

    # ============== mixins ==============

    def save_mixin(self, mixin: Dict[str, Any]) -> Dict[str, Any]:
        created = mixin.get("created_at")
        if isinstance(created, datetime):
            created = created.isoformat()
        conn = sqlite3.connect(self.db_path)
        try:
            conn.execute(
                """INSERT OR REPLACE INTO mixins
                   (id, name, description, properties, target_type_ids, created_at)
                   VALUES (?, ?, ?, ?, ?, ?)""",
                (
                    mixin.get("id", ""),
                    mixin.get("name", ""),
                    mixin.get("description", ""),
                    json.dumps(mixin.get("properties", []), ensure_ascii=False),
                    json.dumps(mixin.get("target_type_ids", []), ensure_ascii=False),
                    created or datetime.now().isoformat(),
                ),
            )
            conn.commit()
            return mixin
        finally:
            conn.close()

    def delete_mixin(self, mixin_id: str) -> bool:
        conn = sqlite3.connect(self.db_path)
        try:
            cursor = conn.execute("DELETE FROM mixins WHERE id = ?", (mixin_id,))
            conn.commit()
            return cursor.rowcount > 0
        finally:
            conn.close()

    def get_mixin(self, mixin_id: str) -> Optional[Dict[str, Any]]:
        conn = sqlite3.connect(self.db_path)
        try:
            cursor = conn.execute("SELECT * FROM mixins WHERE id = ?", (mixin_id,))
            row = cursor.fetchone()
            if not row:
                return None
            return self._row_to_mixin(row)
        finally:
            conn.close()

    def list_mixins(self) -> List[Dict[str, Any]]:
        conn = sqlite3.connect(self.db_path)
        try:
            cursor = conn.execute("SELECT * FROM mixins ORDER BY name")
            return [self._row_to_mixin(r) for r in cursor.fetchall()]
        finally:
            conn.close()

    def attach_mixin_to_type(self, mixin_id: str, type_id: str) -> bool:
        mixin = self.get_mixin(mixin_id)
        if not mixin:
            return False
        targets = list(mixin.get("target_type_ids", []))
        if type_id in targets:
            return True
        targets.append(type_id)
        mixin["target_type_ids"] = targets
        self.save_mixin(mixin)
        return True

    def detach_mixin_from_type(self, mixin_id: str, type_id: str) -> bool:
        mixin = self.get_mixin(mixin_id)
        if not mixin:
            return False
        targets = list(mixin.get("target_type_ids", []))
        if type_id not in targets:
            return True
        targets.remove(type_id)
        mixin["target_type_ids"] = targets
        self.save_mixin(mixin)
        return True

    def list_mixins_for_type(self, type_id: str) -> List[Dict[str, Any]]:
        all_mixins = self.list_mixins()
        return [m for m in all_mixins if type_id in (m.get("target_type_ids") or [])]

    # ============== row → dict ==============

    @staticmethod
    def _row_to_edge(row) -> Dict[str, Any]:
        return {
            "id": row[0],
            "child_type_id": row[1],
            "parent_type_id": row[2],
            "depth": row[3],
            "discriminator": json.loads(row[4]) if row[4] else {},
            "created_at": row[5],
        }

    @staticmethod
    def _row_to_mixin(row) -> Dict[str, Any]:
        return {
            "id": row[0],
            "name": row[1],
            "description": row[2],
            "properties": json.loads(row[3]) if row[3] else [],
            "target_type_ids": json.loads(row[4]) if row[4] else [],
            "created_at": row[5],
        }
