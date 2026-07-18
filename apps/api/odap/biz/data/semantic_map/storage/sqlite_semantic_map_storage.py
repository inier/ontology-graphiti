import sqlite3
import json
import os
import uuid
from typing import Dict, Any, List, Optional
from datetime import datetime

from ..models.semantic_map import (
    SemanticMap, SemanticMapObject, SemanticMapRelation,
    SemanticMapCluster, SemanticMapStatistics, SemanticMapStatus,
)

DEFAULT_DB_DIR = os.path.join(os.getenv("DATA_DIR", os.path.join(os.getcwd(), "data")), "semantic_map")
DEFAULT_DB_PATH = os.path.join(DEFAULT_DB_DIR, "semantic_map.db")


class SQLiteSemanticMapStorage:
    SQLITE_TIMEOUT = 30

    def __init__(self, db_path: str = None):
        if db_path is None:
            os.makedirs(DEFAULT_DB_DIR, exist_ok=True)
            db_path = DEFAULT_DB_PATH
        self.db_path = db_path
        self._init_db()

    def _get_conn(self):
        conn = sqlite3.connect(self.db_path, timeout=self.SQLITE_TIMEOUT)
        conn.execute("PRAGMA journal_mode=WAL")
        conn.execute("PRAGMA busy_timeout=30000")
        return conn

    def _init_db(self):
        db_dir = os.path.dirname(self.db_path)
        if db_dir and not os.path.exists(db_dir):
            os.makedirs(db_dir, exist_ok=True)

        conn = self._get_conn()
        cursor = conn.cursor()

        cursor.execute('''
            CREATE TABLE IF NOT EXISTS semantic_maps (
                id TEXT PRIMARY KEY,
                name TEXT NOT NULL,
                description TEXT DEFAULT '',
                ontology_version_id TEXT NOT NULL,
                ontology_id TEXT NOT NULL,
                scenario_id TEXT,
                status TEXT NOT NULL DEFAULT 'draft',
                objects TEXT DEFAULT '[]',
                relations TEXT DEFAULT '[]',
                clusters TEXT DEFAULT '[]',
                statistics TEXT DEFAULT '{}',
                generation_config TEXT DEFAULT '{}',
                error_message TEXT,
                created_at TEXT NOT NULL,
                created_by TEXT DEFAULT 'system',
                updated_at TEXT
            )
        ''')

        cursor.execute('''
            CREATE INDEX IF NOT EXISTS idx_semantic_maps_version
            ON semantic_maps(ontology_version_id)
        ''')

        cursor.execute('''
            CREATE INDEX IF NOT EXISTS idx_semantic_maps_ontology
            ON semantic_maps(ontology_id)
        ''')

        cursor.execute('''
            CREATE INDEX IF NOT EXISTS idx_semantic_maps_scenario
            ON semantic_maps(scenario_id)
        ''')

        conn.commit()
        conn.close()

    def save(self, semantic_map: SemanticMap) -> str:
        conn = self._get_conn()
        cursor = conn.cursor()
        now = datetime.now().isoformat()

        cursor.execute('''
            INSERT OR REPLACE INTO semantic_maps
            (id, name, description, ontology_version_id, ontology_id, scenario_id,
             status, objects, relations, clusters, statistics, generation_config,
             error_message, created_at, created_by, updated_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        ''', (
            semantic_map.id,
            semantic_map.name,
            semantic_map.description,
            semantic_map.ontology_version_id,
            semantic_map.ontology_id,
            semantic_map.scenario_id,
            semantic_map.status.value,
            self._serialize_json([o.model_dump() for o in semantic_map.objects]),
            self._serialize_json([r.model_dump() for r in semantic_map.relations]),
            self._serialize_json([c.model_dump() for c in semantic_map.clusters]),
            self._serialize_json(semantic_map.statistics.model_dump()),
            self._serialize_json(semantic_map.generation_config),
            semantic_map.error_message,
            semantic_map.created_at.isoformat() if isinstance(semantic_map.created_at, datetime) else semantic_map.created_at,
            semantic_map.created_by,
            now,
        ))

        conn.commit()
        conn.close()
        return semantic_map.id

    def get(self, map_id: str) -> Optional[SemanticMap]:
        conn = self._get_conn()
        cursor = conn.cursor()
        cursor.execute('SELECT * FROM semantic_maps WHERE id = ?', (map_id,))
        row = cursor.fetchone()
        conn.close()
        if not row:
            return None
        return self._row_to_model(row)

    def list_by_version(self, ontology_version_id: str) -> List[SemanticMap]:
        conn = self._get_conn()
        cursor = conn.cursor()
        cursor.execute(
            'SELECT * FROM semantic_maps WHERE ontology_version_id = ? ORDER BY created_at DESC',
            (ontology_version_id,)
        )
        rows = cursor.fetchall()
        conn.close()
        return [self._row_to_model(row) for row in rows]

    def list_by_ontology(self, ontology_id: str) -> List[SemanticMap]:
        conn = self._get_conn()
        cursor = conn.cursor()
        cursor.execute(
            'SELECT * FROM semantic_maps WHERE ontology_id = ? ORDER BY created_at DESC',
            (ontology_id,)
        )
        rows = cursor.fetchall()
        conn.close()
        return [self._row_to_model(row) for row in rows]

    def list_by_scenario(self, scenario_id: str) -> List[SemanticMap]:
        conn = self._get_conn()
        cursor = conn.cursor()
        cursor.execute(
            'SELECT * FROM semantic_maps WHERE scenario_id = ? ORDER BY created_at DESC',
            (scenario_id,)
        )
        rows = cursor.fetchall()
        conn.close()
        return [self._row_to_model(row) for row in rows]

    def list_all(self, limit: int = 100) -> List[SemanticMap]:
        conn = self._get_conn()
        cursor = conn.cursor()
        cursor.execute('SELECT * FROM semantic_maps ORDER BY created_at DESC LIMIT ?', (limit,))
        rows = cursor.fetchall()
        conn.close()
        return [self._row_to_model(row) for row in rows]

    def update_status(self, map_id: str, status: SemanticMapStatus, error_message: str = None) -> bool:
        conn = self._get_conn()
        cursor = conn.cursor()
        now = datetime.now().isoformat()
        cursor.execute('''
            UPDATE semantic_maps SET status = ?, error_message = ?, updated_at = ?
            WHERE id = ?
        ''', (status.value, error_message, now, map_id))
        affected = cursor.rowcount
        conn.commit()
        conn.close()
        return affected > 0

    def delete(self, map_id: str) -> bool:
        conn = self._get_conn()
        cursor = conn.cursor()
        cursor.execute('DELETE FROM semantic_maps WHERE id = ?', (map_id,))
        affected = cursor.rowcount
        conn.commit()
        conn.close()
        return affected > 0

    def _row_to_model(self, row) -> SemanticMap:
        objects_data = self._deserialize_json(row[7]) or []
        relations_data = self._deserialize_json(row[8]) or []
        clusters_data = self._deserialize_json(row[9]) or []
        statistics_data = self._deserialize_json(row[10]) or {}

        return SemanticMap(
            id=row[0],
            name=row[1],
            description=row[2] or "",
            ontology_version_id=row[3],
            ontology_id=row[4],
            scenario_id=row[5],
            status=SemanticMapStatus(row[6]),
            objects=[SemanticMapObject(**o) for o in objects_data],
            relations=[SemanticMapRelation(**r) for r in relations_data],
            clusters=[SemanticMapCluster(**c) for c in clusters_data],
            statistics=SemanticMapStatistics(**statistics_data),
            generation_config=self._deserialize_json(row[11]) or {},
            error_message=row[12],
            created_at=row[13],
            created_by=row[14] or "system",
            updated_at=row[15],
        )

    def _serialize_json(self, data: Any) -> str:
        return json.dumps(data, ensure_ascii=False, default=str)

    def _deserialize_json(self, data: str) -> Any:
        if not data:
            return None
        try:
            return json.loads(data)
        except Exception:
            return None
