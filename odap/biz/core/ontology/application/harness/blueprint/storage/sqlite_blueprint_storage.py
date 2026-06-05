import os
import json
import sqlite3
import uuid
from datetime import datetime
from typing import Dict, Any, List, Optional


class BlueprintStorage:
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
                CREATE TABLE IF NOT EXISTS blueprint_designs (
                    blueprint_id TEXT PRIMARY KEY,
                    name TEXT NOT NULL,
                    description TEXT DEFAULT '',
                    scenario_id TEXT,
                    version INTEGER DEFAULT 1,
                    nodes TEXT DEFAULT '[]',
                    edges TEXT DEFAULT '[]',
                    layout TEXT DEFAULT '{}',
                    is_published INTEGER DEFAULT 0,
                    parent_version_id TEXT,
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL,
                    metadata TEXT DEFAULT '{}'
                );

                CREATE INDEX IF NOT EXISTS idx_bp_scenario ON blueprint_designs(scenario_id);
                CREATE INDEX IF NOT EXISTS idx_bp_published ON blueprint_designs(is_published);
            """)
            conn.commit()
        finally:
            conn.close()

    def save(self, bp_data: Dict[str, Any]) -> Dict[str, Any]:
        conn = self._get_conn()
        try:
            conn.execute("""
                INSERT OR REPLACE INTO blueprint_designs
                (blueprint_id, name, description, scenario_id, version, nodes, edges,
                 layout, is_published, parent_version_id, created_at, updated_at, metadata)
                VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?)
            """, (
                bp_data["blueprint_id"], bp_data["name"], bp_data.get("description", ""),
                bp_data.get("scenario_id"), bp_data.get("version", 1),
                json.dumps(bp_data.get("nodes", []), ensure_ascii=False),
                json.dumps(bp_data.get("edges", []), ensure_ascii=False),
                json.dumps(bp_data.get("layout", {}), ensure_ascii=False),
                1 if bp_data.get("is_published", False) else 0,
                bp_data.get("parent_version_id"),
                bp_data.get("created_at", ""), bp_data.get("updated_at", ""),
                json.dumps(bp_data.get("metadata", {}), ensure_ascii=False),
            ))
            conn.commit()
            return bp_data
        finally:
            conn.close()

    def get(self, blueprint_id: str) -> Optional[Dict[str, Any]]:
        conn = self._get_conn()
        try:
            row = conn.execute(
                "SELECT * FROM blueprint_designs WHERE blueprint_id = ?", (blueprint_id,)
            ).fetchone()
            if not row:
                return None
            return self._row_to_blueprint(row)
        finally:
            conn.close()

    def list_blueprints(self, scenario_id: Optional[str] = None,
                        is_published: Optional[bool] = None,
                        limit: int = 100) -> List[Dict[str, Any]]:
        conn = self._get_conn()
        try:
            query = "SELECT * FROM blueprint_designs WHERE 1=1"
            params = []
            if scenario_id:
                query += " AND scenario_id = ?"
                params.append(scenario_id)
            if is_published is not None:
                query += " AND is_published = ?"
                params.append(1 if is_published else 0)
            query += " ORDER BY updated_at DESC LIMIT ?"
            params.append(limit)
            rows = conn.execute(query, params).fetchall()
            return [self._row_to_blueprint(r) for r in rows]
        finally:
            conn.close()

    def delete(self, blueprint_id: str) -> bool:
        conn = self._get_conn()
        try:
            cursor = conn.execute(
                "DELETE FROM blueprint_designs WHERE blueprint_id = ?", (blueprint_id,)
            )
            conn.commit()
            return cursor.rowcount > 0
        finally:
            conn.close()

    def _row_to_blueprint(self, row) -> Dict[str, Any]:
        return {
            "blueprint_id": row[0], "name": row[1], "description": row[2],
            "scenario_id": row[3], "version": row[4],
            "nodes": json.loads(row[5]) if row[5] else [],
            "edges": json.loads(row[6]) if row[6] else [],
            "layout": json.loads(row[7]) if row[7] else {},
            "is_published": bool(row[8]), "parent_version_id": row[9],
            "created_at": row[10], "updated_at": row[11],
            "metadata": json.loads(row[12]) if row[12] else {},
        }


class BlueprintVersionStorage:
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
                CREATE TABLE IF NOT EXISTS blueprint_version_history (
                    id TEXT PRIMARY KEY,
                    blueprint_id TEXT NOT NULL,
                    snapshot TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    description TEXT DEFAULT ''
                );
                CREATE INDEX IF NOT EXISTS idx_bvh_blueprint ON blueprint_version_history(blueprint_id);
            """)
            conn.commit()
        finally:
            conn.close()

    def save_snapshot(self, blueprint_id: str, snapshot: Dict[str, Any],
                      description: str = "") -> str:
        snapshot_id = f"snap-{uuid.uuid4().hex[:8]}"
        conn = self._get_conn()
        try:
            conn.execute(
                "INSERT INTO blueprint_version_history (id, blueprint_id, snapshot, created_at, description) VALUES (?,?,?,?,?)",
                (snapshot_id, blueprint_id, json.dumps(snapshot, ensure_ascii=False),
                 datetime.now().isoformat(), description),
            )
            conn.commit()
            return snapshot_id
        finally:
            conn.close()

    def list_snapshots(self, blueprint_id: str) -> List[Dict[str, Any]]:
        conn = self._get_conn()
        try:
            rows = conn.execute(
                "SELECT id, blueprint_id, snapshot, created_at, description FROM blueprint_version_history WHERE blueprint_id = ? ORDER BY created_at DESC",
                (blueprint_id,),
            ).fetchall()
            result = []
            for row in rows:
                result.append({
                    "snapshot_id": row[0],
                    "blueprint_id": row[1],
                    "snapshot": json.loads(row[2]) if row[2] else {},
                    "created_at": row[3],
                    "description": row[4],
                })
            return result
        finally:
            conn.close()
