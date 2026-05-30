import os
import json
import sqlite3
import logging
from typing import Dict, Any, List, Optional

logger = logging.getLogger("harness_storage")


class SQLiteHarnessStorage:
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
                CREATE TABLE IF NOT EXISTS harness_sessions (
                    session_id TEXT PRIMARY KEY,
                    name TEXT DEFAULT '',
                    description TEXT DEFAULT '',
                    current_stage TEXT DEFAULT 'data_selection',
                    stage_results TEXT DEFAULT '[]',
                    hitl_confirmations TEXT DEFAULT '[]',
                    agent_tasks TEXT DEFAULT '[]',
                    context_memory TEXT DEFAULT '{}',
                    scenario_id TEXT,
                    workspace_id TEXT,
                    status TEXT DEFAULT 'pending',
                    created_at TEXT DEFAULT '',
                    updated_at TEXT DEFAULT '',
                    requirement TEXT DEFAULT '',
                    sub_tasks TEXT DEFAULT '[]',
                    messages TEXT DEFAULT '[]',
                    planning_output TEXT DEFAULT '{}',
                    ontology_output TEXT DEFAULT '{}',
                    execution_output TEXT DEFAULT '{}'
                );

                CREATE TABLE IF NOT EXISTS ontology_blueprints (
                    blueprint_id TEXT PRIMARY KEY,
                    name TEXT DEFAULT '',
                    description TEXT DEFAULT '',
                    nodes TEXT DEFAULT '[]',
                    edges TEXT DEFAULT '[]',
                    session_id TEXT,
                    version INTEGER DEFAULT 1,
                    created_at TEXT DEFAULT ''
                );

                CREATE INDEX IF NOT EXISTS idx_sessions_status ON harness_sessions(status);
                CREATE INDEX IF NOT EXISTS idx_sessions_scenario ON harness_sessions(scenario_id);
                CREATE INDEX IF NOT EXISTS idx_blueprints_session ON ontology_blueprints(session_id);
            """)
            self._migrate_add_pipeline_columns(conn)
            conn.commit()
        finally:
            conn.close()

    def _migrate_add_pipeline_columns(self, conn):
        cursor = conn.execute("PRAGMA table_info(harness_sessions)")
        existing = {row[1] for row in cursor.fetchall()}
        migrations = [
            ("requirement", "TEXT DEFAULT ''"),
            ("sub_tasks", "TEXT DEFAULT '[]'"),
            ("messages", "TEXT DEFAULT '[]'"),
            ("planning_output", "TEXT DEFAULT '{}'"),
            ("ontology_output", "TEXT DEFAULT '{}'"),
            ("execution_output", "TEXT DEFAULT '{}'"),
        ]
        for col_name, col_type in migrations:
            if col_name not in existing:
                conn.execute(f"ALTER TABLE harness_sessions ADD COLUMN {col_name} {col_type}")

    def save_session(self, session: Dict[str, Any]) -> Dict[str, Any]:
        conn = self._get_conn()
        try:
            conn.execute("""
                INSERT OR REPLACE INTO harness_sessions
                (session_id, name, description, current_stage, stage_results,
                 hitl_confirmations, agent_tasks, context_memory,
                 scenario_id, workspace_id, status, created_at, updated_at,
                 requirement, sub_tasks, messages,
                 planning_output, ontology_output, execution_output)
                VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)
            """, (
                session["session_id"], session.get("name", ""), session.get("description", ""),
                session.get("current_stage", "data_selection"),
                json.dumps(session.get("stage_results", []), ensure_ascii=False),
                json.dumps(session.get("hitl_confirmations", []), ensure_ascii=False),
                json.dumps(session.get("agent_tasks", []), ensure_ascii=False),
                json.dumps(session.get("context_memory", {}), ensure_ascii=False),
                session.get("scenario_id"), session.get("workspace_id"),
                session.get("status", "pending"),
                session.get("created_at", ""), session.get("updated_at", ""),
                session.get("requirement", ""),
                json.dumps(session.get("sub_tasks", []), ensure_ascii=False),
                json.dumps(session.get("messages", []), ensure_ascii=False),
                json.dumps(session.get("planning_output", {}), ensure_ascii=False),
                json.dumps(session.get("ontology_output", {}), ensure_ascii=False),
                json.dumps(session.get("execution_output", {}), ensure_ascii=False),
            ))
            conn.commit()
            return session
        finally:
            conn.close()

    def get_session(self, session_id: str) -> Optional[Dict[str, Any]]:
        conn = self._get_conn()
        try:
            row = conn.execute("SELECT * FROM harness_sessions WHERE session_id = ?", (session_id,)).fetchone()
            if not row:
                return None
            return self._row_to_session(row)
        finally:
            conn.close()

    def list_sessions(self, status: Optional[str] = None, scenario_id: Optional[str] = None) -> List[Dict[str, Any]]:
        conn = self._get_conn()
        try:
            sql = "SELECT * FROM harness_sessions WHERE 1=1"
            params = []
            if status:
                sql += " AND status = ?"
                params.append(status)
            if scenario_id:
                sql += " AND scenario_id = ?"
                params.append(scenario_id)
            sql += " ORDER BY created_at DESC"
            rows = conn.execute(sql, params).fetchall()
            return [self._row_to_session(r) for r in rows]
        finally:
            conn.close()

    def delete_session(self, session_id: str) -> bool:
        conn = self._get_conn()
        try:
            cursor = conn.execute("DELETE FROM harness_sessions WHERE session_id = ?", (session_id,))
            conn.commit()
            return cursor.rowcount > 0
        finally:
            conn.close()

    def _row_to_session(self, row) -> Dict[str, Any]:
        return {
            "session_id": row[0], "name": row[1], "description": row[2],
            "current_stage": row[3],
            "stage_results": json.loads(row[4]) if row[4] else [],
            "hitl_confirmations": json.loads(row[5]) if row[5] else [],
            "agent_tasks": json.loads(row[6]) if row[6] else [],
            "context_memory": json.loads(row[7]) if row[7] else {},
            "scenario_id": row[8], "workspace_id": row[9],
            "status": row[10], "created_at": row[11], "updated_at": row[12],
            "requirement": row[13] if len(row) > 13 else "",
            "sub_tasks": json.loads(row[14]) if len(row) > 14 and row[14] else [],
            "messages": json.loads(row[15]) if len(row) > 15 and row[15] else [],
            "planning_output": json.loads(row[16]) if len(row) > 16 and row[16] else {},
            "ontology_output": json.loads(row[17]) if len(row) > 17 and row[17] else {},
            "execution_output": json.loads(row[18]) if len(row) > 18 and row[18] else {},
        }

    def save_blueprint(self, bp: Dict[str, Any]) -> Dict[str, Any]:
        conn = self._get_conn()
        try:
            conn.execute("""
                INSERT OR REPLACE INTO ontology_blueprints
                (blueprint_id, name, description, nodes, edges, session_id, version, created_at)
                VALUES (?,?,?,?,?,?,?,?)
            """, (
                bp["blueprint_id"], bp.get("name", ""), bp.get("description", ""),
                json.dumps(bp.get("nodes", []), ensure_ascii=False),
                json.dumps(bp.get("edges", []), ensure_ascii=False),
                bp.get("session_id"), bp.get("version", 1),
                bp.get("created_at", ""),
            ))
            conn.commit()
            return bp
        finally:
            conn.close()

    def get_blueprint(self, blueprint_id: str) -> Optional[Dict[str, Any]]:
        conn = self._get_conn()
        try:
            row = conn.execute("SELECT * FROM ontology_blueprints WHERE blueprint_id = ?", (blueprint_id,)).fetchone()
            if not row:
                return None
            return {
                "blueprint_id": row[0], "name": row[1], "description": row[2],
                "nodes": json.loads(row[3]) if row[3] else [],
                "edges": json.loads(row[4]) if row[4] else [],
                "session_id": row[5], "version": row[6], "created_at": row[7],
            }
        finally:
            conn.close()

    def list_blueprints(self, session_id: Optional[str] = None) -> List[Dict[str, Any]]:
        conn = self._get_conn()
        try:
            if session_id:
                rows = conn.execute("SELECT * FROM ontology_blueprints WHERE session_id = ? ORDER BY created_at DESC", (session_id,)).fetchall()
            else:
                rows = conn.execute("SELECT * FROM ontology_blueprints ORDER BY created_at DESC").fetchall()
            return [{
                "blueprint_id": r[0], "name": r[1], "description": r[2],
                "nodes": json.loads(r[3]) if r[3] else [],
                "edges": json.loads(r[4]) if r[4] else [],
                "session_id": r[5], "version": r[6], "created_at": r[7],
            } for r in rows]
        finally:
            conn.close()

    def delete_blueprint(self, blueprint_id: str) -> bool:
        conn = self._get_conn()
        try:
            cursor = conn.execute("DELETE FROM ontology_blueprints WHERE blueprint_id = ?", (blueprint_id,))
            conn.commit()
            return cursor.rowcount > 0
        finally:
            conn.close()
