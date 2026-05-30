import os
import json
import sqlite3
import uuid
from datetime import datetime


class MemoryGraphSyncStorage:
    def __init__(self, db_path=None):
        self.db_path = db_path or os.path.join(
            os.environ.get("DATA_DIR", os.path.join(os.getcwd(), "data")),
            "ontology_session.db"
        )
        self._init_db()

    def _init_db(self):
        conn = sqlite3.connect(self.db_path)
        c = conn.cursor()
        c.execute("""CREATE TABLE IF NOT EXISTS memory_graph_sync_map (
            sync_id TEXT PRIMARY KEY,
            memory_id TEXT NOT NULL,
            graph_entity_id TEXT,
            graph_episode_name TEXT,
            sync_type TEXT DEFAULT 'memory_to_graph',
            sync_status TEXT DEFAULT 'synced',
            last_synced_at TEXT NOT NULL,
            metadata TEXT DEFAULT '{}'
        )""")
        c.execute("CREATE INDEX IF NOT EXISTS idx_sync_memory ON memory_graph_sync_map(memory_id)")
        c.execute("CREATE INDEX IF NOT EXISTS idx_sync_entity ON memory_graph_sync_map(graph_entity_id)")
        conn.commit()
        conn.close()

    def save_sync(self, memory_id, graph_entity_id, episode_name, sync_type, metadata=None):
        conn = sqlite3.connect(self.db_path)
        c = conn.cursor()
        c.execute("SELECT sync_id FROM memory_graph_sync_map WHERE memory_id = ?", (memory_id,))
        existing = c.fetchone()
        if existing:
            sync_id = existing[0]
            c.execute("""UPDATE memory_graph_sync_map
                SET graph_entity_id = ?, graph_episode_name = ?, sync_type = ?,
                    sync_status = ?, last_synced_at = ?, metadata = ?
                WHERE memory_id = ?""",
                (graph_entity_id, episode_name, sync_type, "synced",
                 datetime.now().isoformat(), json.dumps(metadata or {}, ensure_ascii=False),
                 memory_id))
        else:
            sync_id = f"sync-{uuid.uuid4().hex[:8]}"
            c.execute("""INSERT INTO memory_graph_sync_map
                (sync_id, memory_id, graph_entity_id, graph_episode_name, sync_type, sync_status, last_synced_at, metadata)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
                (sync_id, memory_id, graph_entity_id, episode_name, sync_type, "synced",
                 datetime.now().isoformat(), json.dumps(metadata or {}, ensure_ascii=False)))
        conn.commit()
        conn.close()
        return sync_id

    def get_by_memory(self, memory_id):
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        c = conn.cursor()
        c.execute("SELECT * FROM memory_graph_sync_map WHERE memory_id = ?", (memory_id,))
        row = c.fetchone()
        conn.close()
        return dict(row) if row else None

    def get_by_graph_entity(self, graph_entity_id):
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        c = conn.cursor()
        c.execute("SELECT * FROM memory_graph_sync_map WHERE graph_entity_id = ?", (graph_entity_id,))
        row = c.fetchone()
        conn.close()
        return dict(row) if row else None

    def update_sync_status(self, memory_id, status, metadata=None):
        conn = sqlite3.connect(self.db_path)
        c = conn.cursor()
        c.execute("UPDATE memory_graph_sync_map SET sync_status = ?, last_synced_at = ?, metadata = ? WHERE memory_id = ?",
                  (status, datetime.now().isoformat(), json.dumps(metadata or {}, ensure_ascii=False), memory_id))
        affected = c.rowcount
        conn.commit()
        conn.close()
        return affected > 0

    def list_unsynced(self, limit=100):
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        c = conn.cursor()
        c.execute("SELECT * FROM memory_graph_sync_map WHERE sync_status != 'synced' LIMIT ?", (limit,))
        rows = c.fetchall()
        conn.close()
        return [dict(r) for r in rows]
