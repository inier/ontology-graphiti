"""T059 SQLiteAssistantStorage — AI suggestion + assistant session storage.

Follows AGENTS.md rules:
- Rule 8: SQLite no connection pool, connect/close per operation
- Complex fields (Dict/List) stored as JSON TEXT
- Enum stored as .value string
- datetime stored as ISO string
"""
import json
import os
import sqlite3
import uuid
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

DEFAULT_DB_DIR = os.environ.get(
    "DATA_DIR", os.path.join(os.getcwd(), "data")
)
DEFAULT_DB_PATH = os.path.join(DEFAULT_DB_DIR, "ontology_assistant.db")


def _safe_json_loads(raw: Any, default: Any) -> Any:
    if raw is None:
        return default
    if isinstance(raw, (dict, list)):
        return raw
    try:
        return json.loads(raw)
    except (json.JSONDecodeError, TypeError, ValueError):
        return default


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


class SQLiteAssistantStorage:
    """Storage for AI suggestions and assistant sessions."""

    def __init__(self, db_path: str = None):
        if db_path is None:
            os.makedirs(DEFAULT_DB_DIR, exist_ok=True)
            db_path = DEFAULT_DB_PATH
        self.db_path = db_path
        self._init_db()

    def _get_conn(self):
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        return conn

    def _init_db(self):
        conn = self._get_conn()
        try:
            self._create_ai_suggestions_table(conn)
            self._create_ai_assistant_sessions_table(conn)
            conn.commit()
        finally:
            conn.close()

    @staticmethod
    def _create_ai_suggestions_table(conn):
        conn.execute("""
            CREATE TABLE IF NOT EXISTS ai_suggestions (
                suggestion_id TEXT PRIMARY KEY,
                ontology_id TEXT NOT NULL,
                target_type TEXT NOT NULL,
                target_id TEXT,
                suggestion_category TEXT NOT NULL,
                content TEXT NOT NULL DEFAULT '{}',
                source TEXT NOT NULL,
                confidence REAL DEFAULT 0.0,
                status TEXT DEFAULT 'pending',
                rejection_reason TEXT,
                session_id TEXT,
                created_at TEXT NOT NULL,
                resolved_at TEXT
            )
        """)
        conn.execute(
            "CREATE INDEX IF NOT EXISTS idx_suggestions_ontology ON ai_suggestions(ontology_id)"
        )
        conn.execute(
            "CREATE INDEX IF NOT EXISTS idx_suggestions_status ON ai_suggestions(status)"
        )

    @staticmethod
    def _create_ai_assistant_sessions_table(conn):
        conn.execute("""
            CREATE TABLE IF NOT EXISTS ai_assistant_sessions (
                session_id TEXT PRIMARY KEY,
                ontology_id TEXT NOT NULL,
                user_id TEXT NOT NULL,
                context_type TEXT NOT NULL,
                context_id TEXT,
                messages TEXT NOT NULL DEFAULT '[]',
                tool_calls TEXT NOT NULL DEFAULT '[]',
                hitl_pending INTEGER DEFAULT 0,
                status TEXT DEFAULT 'active',
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL
            )
        """)
        conn.execute(
            "CREATE INDEX IF NOT EXISTS idx_sessions_ontology ON ai_assistant_sessions(ontology_id)"
        )

    # ── AISuggestion CRUD ──────────────────────────────────────────

    def save_suggestion(self, suggestion: Dict[str, Any]) -> Dict[str, Any]:
        sid = suggestion.get("suggestion_id") or str(uuid.uuid4())
        now = _now_iso()
        conn = self._get_conn()
        try:
            conn.execute(
                """
                INSERT OR REPLACE INTO ai_suggestions
                    (suggestion_id, ontology_id, target_type, target_id,
                     suggestion_category, content, source, confidence,
                     status, rejection_reason, session_id, created_at, resolved_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    sid,
                    suggestion["ontology_id"],
                    suggestion["target_type"],
                    suggestion.get("target_id"),
                    suggestion["suggestion_category"],
                    json.dumps(suggestion.get("content", {}), ensure_ascii=False),
                    suggestion["source"],
                    suggestion.get("confidence", 0.0),
                    suggestion.get("status", "pending"),
                    suggestion.get("rejection_reason"),
                    suggestion.get("session_id"),
                    suggestion.get("created_at", now),
                    suggestion.get("resolved_at"),
                ),
            )
            conn.commit()
        finally:
            conn.close()
        result = dict(suggestion)
        result["suggestion_id"] = sid
        return result

    def get_suggestion(self, suggestion_id: str) -> Optional[Dict[str, Any]]:
        conn = self._get_conn()
        try:
            row = conn.execute(
                "SELECT * FROM ai_suggestions WHERE suggestion_id = ?",
                (suggestion_id,),
            ).fetchone()
            if row is None:
                return None
            return self._parse_suggestion_row(row)
        finally:
            conn.close()

    def list_suggestions(
        self,
        ontology_id: Optional[str] = None,
        status: Optional[str] = None,
    ) -> List[Dict[str, Any]]:
        query = "SELECT * FROM ai_suggestions WHERE 1=1"
        params: List[Any] = []
        if ontology_id:
            query += " AND ontology_id = ?"
            params.append(ontology_id)
        if status:
            query += " AND status = ?"
            params.append(status)
        query += " ORDER BY created_at DESC"
        conn = self._get_conn()
        try:
            rows = conn.execute(query, params).fetchall()
            return [self._parse_suggestion_row(r) for r in rows]
        finally:
            conn.close()

    def update_suggestion_status(
        self,
        suggestion_id: str,
        status: str,
        rejection_reason: Optional[str] = None,
    ) -> bool:
        now = _now_iso()
        conn = self._get_conn()
        try:
            cursor = conn.execute(
                """
                UPDATE ai_suggestions
                SET status = ?, rejection_reason = ?, resolved_at = ?
                WHERE suggestion_id = ?
                """,
                (status, rejection_reason, now, suggestion_id),
            )
            conn.commit()
            return cursor.rowcount > 0
        finally:
            conn.close()

    def delete_suggestion(self, suggestion_id: str) -> bool:
        conn = self._get_conn()
        try:
            cursor = conn.execute(
                "DELETE FROM ai_suggestions WHERE suggestion_id = ?",
                (suggestion_id,),
            )
            conn.commit()
            return cursor.rowcount > 0
        finally:
            conn.close()

    @staticmethod
    def _parse_suggestion_row(row: sqlite3.Row) -> Dict[str, Any]:
        d = dict(row)
        d["content"] = _safe_json_loads(d.get("content"), {})
        return d

    # ── AIAssistantSession CRUD ───────────────────────────────────

    def save_session(self, session: Dict[str, Any]) -> Dict[str, Any]:
        sid = session.get("session_id") or str(uuid.uuid4())
        now = _now_iso()
        conn = self._get_conn()
        try:
            conn.execute(
                """
                INSERT OR REPLACE INTO ai_assistant_sessions
                    (session_id, ontology_id, user_id, context_type, context_id,
                     messages, tool_calls, hitl_pending, status,
                     created_at, updated_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    sid,
                    session["ontology_id"],
                    session["user_id"],
                    session["context_type"],
                    session.get("context_id"),
                    json.dumps(session.get("messages", []), ensure_ascii=False),
                    json.dumps(session.get("tool_calls", []), ensure_ascii=False),
                    1 if session.get("hitl_pending", False) else 0,
                    session.get("status", "active"),
                    session.get("created_at", now),
                    session.get("updated_at", now),
                ),
            )
            conn.commit()
        finally:
            conn.close()
        result = dict(session)
        result["session_id"] = sid
        return result

    def get_session(self, session_id: str) -> Optional[Dict[str, Any]]:
        conn = self._get_conn()
        try:
            row = conn.execute(
                "SELECT * FROM ai_assistant_sessions WHERE session_id = ?",
                (session_id,),
            ).fetchone()
            if row is None:
                return None
            return self._parse_session_row(row)
        finally:
            conn.close()

    def list_sessions(
        self, ontology_id: Optional[str] = None
    ) -> List[Dict[str, Any]]:
        query = "SELECT * FROM ai_assistant_sessions WHERE 1=1"
        params: List[Any] = []
        if ontology_id:
            query += " AND ontology_id = ?"
            params.append(ontology_id)
        query += " ORDER BY created_at DESC"
        conn = self._get_conn()
        try:
            rows = conn.execute(query, params).fetchall()
            return [self._parse_session_row(r) for r in rows]
        finally:
            conn.close()

    def update_session(
        self,
        session_id: str,
        messages: Optional[List[Dict]] = None,
        tool_calls: Optional[List[Dict]] = None,
        hitl_pending: Optional[bool] = None,
        status: Optional[str] = None,
    ) -> bool:
        sets: List[str] = []
        params: List[Any] = []
        if messages is not None:
            sets.append("messages = ?")
            params.append(json.dumps(messages, ensure_ascii=False))
        if tool_calls is not None:
            sets.append("tool_calls = ?")
            params.append(json.dumps(tool_calls, ensure_ascii=False))
        if hitl_pending is not None:
            sets.append("hitl_pending = ?")
            params.append(1 if hitl_pending else 0)
        if status is not None:
            sets.append("status = ?")
            params.append(status)
        if not sets:
            return False
        sets.append("updated_at = ?")
        params.append(_now_iso())
        params.append(session_id)
        conn = self._get_conn()
        try:
            cursor = conn.execute(
                f"UPDATE ai_assistant_sessions SET {', '.join(sets)} WHERE session_id = ?",
                params,
            )
            conn.commit()
            return cursor.rowcount > 0
        finally:
            conn.close()

    def delete_session(self, session_id: str) -> bool:
        conn = self._get_conn()
        try:
            cursor = conn.execute(
                "DELETE FROM ai_assistant_sessions WHERE session_id = ?",
                (session_id,),
            )
            conn.commit()
            return cursor.rowcount > 0
        finally:
            conn.close()

    @staticmethod
    def _parse_session_row(row: sqlite3.Row) -> Dict[str, Any]:
        d = dict(row)
        d["messages"] = _safe_json_loads(d.get("messages"), [])
        d["tool_calls"] = _safe_json_loads(d.get("tool_calls"), [])
        d["hitl_pending"] = bool(d.get("hitl_pending", 0))
        return d
