import sqlite3
import json
import os
from typing import Dict, Any, List, Optional
from datetime import datetime
from ..models.types import (
    AbutionGraphSnapshot, TemporalNode, PatternNode, ForceNode, ActionNode,
    TemporalDimension, PatternType, ForceType, ActionDimension,
)

DEFAULT_DB_DIR = os.environ.get("DATA_DIR", os.path.join(os.getcwd(), "data"))
DEFAULT_DB_PATH = os.path.join(DEFAULT_DB_DIR, "abution_graph.db")


class SQLiteAbutionStorage:
    def __init__(self, db_path: str = None):
        if db_path is None:
            os.makedirs(DEFAULT_DB_DIR, exist_ok=True)
            db_path = DEFAULT_DB_PATH
        self.db_path = db_path
        self._init_db()

    def _init_db(self):
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS abution_graph_snapshots (
                snapshot_id TEXT PRIMARY KEY,
                name TEXT NOT NULL,
                temporal_nodes TEXT DEFAULT '[]',
                pattern_nodes TEXT DEFAULT '[]',
                force_nodes TEXT DEFAULT '[]',
                action_nodes TEXT DEFAULT '[]',
                cross_dimension_links TEXT DEFAULT '[]',
                created_at TEXT NOT NULL
            )
        ''')
        conn.commit()
        conn.close()

    def _serialize(self, data) -> str:
        return json.dumps(data, ensure_ascii=False, default=str)

    def _deserialize(self, data: str) -> Any:
        if not data:
            return []
        try:
            return json.loads(data)
        except (json.JSONDecodeError, TypeError, ValueError):
            return []

    def _snapshot_to_dict(self, snapshot: AbutionGraphSnapshot) -> Dict[str, Any]:
        return {
            "snapshot_id": snapshot.snapshot_id,
            "name": snapshot.name,
            "temporal_nodes": self._serialize([
                {"node_id": n.node_id, "dimension": n.dimension.value,
                 "timestamp": n.timestamp, "description": n.description,
                 "confidence": n.confidence, "metadata": n.metadata}
                for n in snapshot.temporal_nodes
            ]),
            "pattern_nodes": self._serialize([
                {"pattern_id": n.pattern_id, "pattern_type": n.pattern_type.value,
                 "name": n.name, "description": n.description,
                 "evidence": n.evidence, "strength": n.strength, "metadata": n.metadata}
                for n in snapshot.pattern_nodes
            ]),
            "force_nodes": self._serialize([
                {"force_id": n.force_id, "force_type": n.force_type.value,
                 "name": n.name, "magnitude": n.magnitude,
                 "direction": n.direction, "description": n.description, "metadata": n.metadata}
                for n in snapshot.force_nodes
            ]),
            "action_nodes": self._serialize([
                {"action_id": n.action_id, "dimension": n.dimension.value,
                 "name": n.name, "trigger_condition": n.trigger_condition,
                 "effect": n.effect, "priority": n.priority, "metadata": n.metadata}
                for n in snapshot.action_nodes
            ]),
            "cross_dimension_links": self._serialize(snapshot.cross_dimension_links),
            "created_at": snapshot.created_at,
        }

    def _row_to_snapshot(self, row) -> AbutionGraphSnapshot:
        temporal_data = self._deserialize(row["temporal_nodes"])
        pattern_data = self._deserialize(row["pattern_nodes"])
        force_data = self._deserialize(row["force_nodes"])
        action_data = self._deserialize(row["action_nodes"])
        links_data = self._deserialize(row["cross_dimension_links"])

        temporal_nodes = [
            TemporalNode(
                node_id=n["node_id"], dimension=TemporalDimension(n["dimension"]),
                timestamp=n["timestamp"], description=n["description"],
                confidence=n.get("confidence", 1.0), metadata=n.get("metadata", {})
            ) for n in temporal_data
        ]
        pattern_nodes = [
            PatternNode(
                pattern_id=n["pattern_id"], pattern_type=PatternType(n["pattern_type"]),
                name=n["name"], description=n["description"],
                evidence=n.get("evidence", []), strength=n.get("strength", 0.0),
                metadata=n.get("metadata", {})
            ) for n in pattern_data
        ]
        force_nodes = [
            ForceNode(
                force_id=n["force_id"], force_type=ForceType(n["force_type"]),
                name=n["name"], magnitude=n.get("magnitude", 0.0),
                direction=n.get("direction", 0.0), description=n.get("description", ""),
                metadata=n.get("metadata", {})
            ) for n in force_data
        ]
        action_nodes = [
            ActionNode(
                action_id=n["action_id"], dimension=ActionDimension(n["dimension"]),
                name=n["name"], trigger_condition=n.get("trigger_condition", ""),
                effect=n.get("effect", ""), priority=n.get("priority", 0),
                metadata=n.get("metadata", {})
            ) for n in action_data
        ]

        return AbutionGraphSnapshot(
            snapshot_id=row["snapshot_id"], name=row["name"],
            temporal_nodes=temporal_nodes, pattern_nodes=pattern_nodes,
            force_nodes=force_nodes, action_nodes=action_nodes,
            cross_dimension_links=links_data if isinstance(links_data, list) else [],
            created_at=row["created_at"],
        )

    def save(self, snapshot: AbutionGraphSnapshot) -> None:
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        data = self._snapshot_to_dict(snapshot)
        cursor.execute('''
            INSERT OR REPLACE INTO abution_graph_snapshots
            (snapshot_id, name, temporal_nodes, pattern_nodes, force_nodes,
             action_nodes, cross_dimension_links, created_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        ''', (
            data["snapshot_id"], data["name"], data["temporal_nodes"],
            data["pattern_nodes"], data["force_nodes"], data["action_nodes"],
            data["cross_dimension_links"], data["created_at"],
        ))
        conn.commit()
        conn.close()

    def get(self, snapshot_id: str) -> Optional[AbutionGraphSnapshot]:
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        cursor.execute('SELECT * FROM abution_graph_snapshots WHERE snapshot_id = ?', (snapshot_id,))
        row = cursor.fetchone()
        conn.close()
        if not row:
            return None
        return self._row_to_snapshot(row)

    def list(self, limit: int = 100) -> List[AbutionGraphSnapshot]:
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        cursor.execute(
            'SELECT * FROM abution_graph_snapshots ORDER BY created_at DESC LIMIT ?',
            (limit,)
        )
        rows = cursor.fetchall()
        conn.close()
        return [self._row_to_snapshot(row) for row in rows]

    def delete(self, snapshot_id: str) -> bool:
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        cursor.execute('DELETE FROM abution_graph_snapshots WHERE snapshot_id = ?', (snapshot_id,))
        affected = cursor.rowcount
        conn.commit()
        conn.close()
        return affected > 0
