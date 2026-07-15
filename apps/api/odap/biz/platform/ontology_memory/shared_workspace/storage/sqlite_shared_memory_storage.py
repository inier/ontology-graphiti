import os
import json
import sqlite3
import uuid
from datetime import datetime


class SharedMemoryStorage:
    def __init__(self, db_path=None):
        self.db_path = db_path or os.path.join(
            os.environ.get("DATA_DIR", os.path.join(os.getcwd(), "data")),
            "ontology_session.db"
        )
        self._init_db()

    def _init_db(self):
        conn = sqlite3.connect(self.db_path)
        c = conn.cursor()
        c.execute("""CREATE TABLE IF NOT EXISTS shared_contexts (
            context_id TEXT PRIMARY KEY,
            name TEXT NOT NULL,
            description TEXT DEFAULT '',
            scenario_id TEXT,
            session_id TEXT,
            shared_state TEXT DEFAULT '{}',
            version INTEGER DEFAULT 1,
            is_active INTEGER DEFAULT 1,
            created_at TEXT NOT NULL,
            updated_at TEXT NOT NULL
        )""")
        c.execute("""CREATE TABLE IF NOT EXISTS agent_states (
            state_id TEXT PRIMARY KEY,
            context_id TEXT NOT NULL,
            agent_id TEXT NOT NULL,
            agent_role TEXT DEFAULT '',
            state_data TEXT DEFAULT '{}',
            last_heartbeat TEXT,
            is_active INTEGER DEFAULT 1,
            created_at TEXT NOT NULL,
            updated_at TEXT NOT NULL,
            FOREIGN KEY (context_id) REFERENCES shared_contexts(context_id)
        )""")
        c.execute("""CREATE TABLE IF NOT EXISTS shared_events (
            event_id TEXT PRIMARY KEY,
            context_id TEXT NOT NULL,
            agent_id TEXT NOT NULL,
            event_type TEXT NOT NULL,
            event_data TEXT DEFAULT '{}',
            target_agent_id TEXT,
            is_consumed INTEGER DEFAULT 0,
            created_at TEXT NOT NULL,
            FOREIGN KEY (context_id) REFERENCES shared_contexts(context_id)
        )""")
        c.execute("CREATE INDEX IF NOT EXISTS idx_ctx_scenario ON shared_contexts(scenario_id)")
        c.execute("CREATE INDEX IF NOT EXISTS idx_agent_ctx ON agent_states(context_id)")
        c.execute("CREATE INDEX IF NOT EXISTS idx_events_ctx ON shared_events(context_id)")
        c.execute("CREATE INDEX IF NOT EXISTS idx_events_consumed ON shared_events(is_consumed)")
        conn.commit()
        conn.close()

    def save_context(self, ctx_data):
        conn = sqlite3.connect(self.db_path)
        c = conn.cursor()
        c.execute("""INSERT OR REPLACE INTO shared_contexts
            (context_id, name, description, scenario_id, session_id, shared_state,
             version, is_active, created_at, updated_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (ctx_data["context_id"], ctx_data["name"], ctx_data.get("description", ""),
             ctx_data.get("scenario_id"), ctx_data.get("session_id"),
             json.dumps(ctx_data.get("shared_state", {}), ensure_ascii=False),
             ctx_data.get("version", 1), 1 if ctx_data.get("is_active", True) else 0,
             ctx_data.get("created_at", ""), ctx_data.get("updated_at", "")))
        conn.commit()
        conn.close()

    def get_context(self, context_id):
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        c = conn.cursor()
        c.execute("SELECT * FROM shared_contexts WHERE context_id = ?", (context_id,))
        row = c.fetchone()
        conn.close()
        return dict(row) if row else None

    def list_contexts(self, scenario_id=None, is_active=None):
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        c = conn.cursor()
        query = "SELECT * FROM shared_contexts WHERE 1=1"
        params = []
        if scenario_id:
            query += " AND scenario_id = ?"
            params.append(scenario_id)
        if is_active is not None:
            query += " AND is_active = ?"
            params.append(1 if is_active else 0)
        c.execute(query, params)
        rows = c.fetchall()
        conn.close()
        return [dict(r) for r in rows]

    def delete_context(self, context_id):
        conn = sqlite3.connect(self.db_path)
        c = conn.cursor()
        c.execute("DELETE FROM shared_events WHERE context_id = ?", (context_id,))
        c.execute("DELETE FROM agent_states WHERE context_id = ?", (context_id,))
        c.execute("DELETE FROM shared_contexts WHERE context_id = ?", (context_id,))
        affected = c.rowcount
        conn.commit()
        conn.close()
        return affected > 0

    def save_agent_state(self, state_data):
        conn = sqlite3.connect(self.db_path)
        c = conn.cursor()
        c.execute("""INSERT OR REPLACE INTO agent_states
            (state_id, context_id, agent_id, agent_role, state_data, last_heartbeat,
             is_active, created_at, updated_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (state_data["state_id"], state_data["context_id"], state_data["agent_id"],
             state_data.get("agent_role", ""), json.dumps(state_data.get("state_data", {}), ensure_ascii=False),
             state_data.get("last_heartbeat", ""),
             1 if state_data.get("is_active", True) else 0,
             state_data.get("created_at", ""), state_data.get("updated_at", "")))
        conn.commit()
        conn.close()

    def get_agent_state(self, context_id, agent_id):
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        c = conn.cursor()
        c.execute("SELECT * FROM agent_states WHERE context_id = ? AND agent_id = ?",
                  (context_id, agent_id))
        row = c.fetchone()
        conn.close()
        return dict(row) if row else None

    def list_agent_states(self, context_id):
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        c = conn.cursor()
        c.execute("SELECT * FROM agent_states WHERE context_id = ? AND is_active = 1", (context_id,))
        rows = c.fetchall()
        conn.close()
        return [dict(r) for r in rows]

    def save_event(self, event_data):
        conn = sqlite3.connect(self.db_path)
        c = conn.cursor()
        c.execute("""INSERT INTO shared_events
            (event_id, context_id, agent_id, event_type, event_data, target_agent_id,
             is_consumed, created_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
            (event_data["event_id"], event_data["context_id"], event_data["agent_id"],
             event_data["event_type"], json.dumps(event_data.get("event_data", {}), ensure_ascii=False),
             event_data.get("target_agent_id"), 0, event_data.get("created_at", "")))
        conn.commit()
        conn.close()

    def get_pending_events(self, context_id, agent_id=None, limit=100):
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        c = conn.cursor()
        if agent_id:
            c.execute("""SELECT * FROM shared_events
                WHERE context_id = ? AND is_consumed = 0
                AND (target_agent_id = ? OR target_agent_id IS NULL)
                ORDER BY created_at ASC LIMIT ?""",
                (context_id, agent_id, limit))
        else:
            c.execute("""SELECT * FROM shared_events
                WHERE context_id = ? AND is_consumed = 0
                ORDER BY created_at ASC LIMIT ?""",
                (context_id, limit))
        rows = c.fetchall()
        conn.close()
        return [dict(r) for r in rows]

    def consume_event(self, event_id):
        conn = sqlite3.connect(self.db_path)
        c = conn.cursor()
        c.execute("UPDATE shared_events SET is_consumed = 1 WHERE event_id = ?", (event_id,))
        affected = c.rowcount
        conn.commit()
        conn.close()
        return affected > 0
