import sqlite3
import json
import os
import uuid
from typing import Dict, Any, List, Optional
from datetime import datetime

from ..models.extraction_task import ExtractionTask, ExtractionStatus

DEFAULT_DB_DIR = os.path.join(os.getenv("DATA_DIR", os.path.join(os.getcwd(), "data")), "hyper_extract")
DEFAULT_DB_PATH = os.path.join(DEFAULT_DB_DIR, "hyper_extract.db")


class SQLiteExtractionStorage:
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
            CREATE TABLE IF NOT EXISTS extraction_tasks (
                task_id TEXT PRIMARY KEY,
                text_hash TEXT NOT NULL,
                ontology_id TEXT NOT NULL,
                status TEXT NOT NULL DEFAULT 'pending',
                result TEXT,
                created_at TEXT NOT NULL,
                updated_at TEXT
            )
        ''')

        cursor.execute('''
            CREATE INDEX IF NOT EXISTS idx_extraction_tasks_ontology
            ON extraction_tasks(ontology_id)
        ''')

        cursor.execute('''
            CREATE INDEX IF NOT EXISTS idx_extraction_tasks_status
            ON extraction_tasks(status)
        ''')

        cursor.execute('''
            CREATE TABLE IF NOT EXISTS extraction_sessions (
                session_id TEXT PRIMARY KEY,
                ontology_id TEXT NOT NULL,
                extraction_type TEXT NOT NULL,
                input_data TEXT,
                result_data TEXT,
                status TEXT NOT NULL DEFAULT 'pending',
                conflicts TEXT,
                channel_b_status TEXT,
                created_at TEXT NOT NULL,
                updated_at TEXT
            )
        ''')

        cursor.execute('''
            CREATE INDEX IF NOT EXISTS idx_extraction_sessions_ontology
            ON extraction_sessions(ontology_id)
        ''')

        cursor.execute('''
            CREATE INDEX IF NOT EXISTS idx_extraction_sessions_status
            ON extraction_sessions(status)
        ''')

        conn.commit()
        conn.close()

    def save_task(self, task: ExtractionTask) -> str:
        conn = self._get_conn()
        cursor = conn.cursor()
        now = datetime.now().isoformat()

        cursor.execute('''
            INSERT OR REPLACE INTO extraction_tasks
            (task_id, text_hash, ontology_id, status, result, created_at, updated_at)
            VALUES (?, ?, ?, ?, ?, ?, ?)
        ''', (
            task.task_id,
            task.text_hash,
            task.ontology_id,
            task.status.value,
            self._serialize_json(task.result) if task.result else None,
            task.created_at.isoformat() if isinstance(task.created_at, datetime) else task.created_at,
            now,
        ))

        conn.commit()
        conn.close()
        return task.task_id

    def get_task(self, task_id: str) -> Optional[ExtractionTask]:
        conn = self._get_conn()
        cursor = conn.cursor()
        cursor.execute('SELECT * FROM extraction_tasks WHERE task_id = ?', (task_id,))
        row = cursor.fetchone()
        conn.close()
        if not row:
            return None
        return self._row_to_model(row)

    def list_tasks(
        self,
        ontology_id: Optional[str] = None,
        status: Optional[ExtractionStatus] = None,
        limit: int = 100,
    ) -> List[ExtractionTask]:
        conn = self._get_conn()
        cursor = conn.cursor()

        query = 'SELECT * FROM extraction_tasks WHERE 1=1'
        params: List[Any] = []

        if ontology_id:
            query += ' AND ontology_id = ?'
            params.append(ontology_id)
        if status:
            query += ' AND status = ?'
            params.append(status.value)

        query += ' ORDER BY created_at DESC LIMIT ?'
        params.append(limit)

        cursor.execute(query, params)
        rows = cursor.fetchall()
        conn.close()
        return [self._row_to_model(row) for row in rows]

    def update_status(self, task_id: str, status: ExtractionStatus, result: Optional[Dict[str, Any]] = None) -> bool:
        conn = self._get_conn()
        cursor = conn.cursor()
        now = datetime.now().isoformat()

        if result is not None:
            cursor.execute('''
                UPDATE extraction_tasks SET status = ?, result = ?, updated_at = ?
                WHERE task_id = ?
            ''', (status.value, self._serialize_json(result), now, task_id))
        else:
            cursor.execute('''
                UPDATE extraction_tasks SET status = ?, updated_at = ?
                WHERE task_id = ?
            ''', (status.value, now, task_id))

        affected = cursor.rowcount
        conn.commit()
        conn.close()
        return affected > 0

    def _row_to_model(self, row) -> ExtractionTask:
        return ExtractionTask(
            task_id=row[0],
            text_hash=row[1],
            ontology_id=row[2],
            status=ExtractionStatus(row[3]),
            result=self._deserialize_json(row[4]),
            created_at=row[5],
            updated_at=row[6],
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

    # ------------------------------------------------------------------
    # Extraction session management (used by ExtractService)
    # ------------------------------------------------------------------

    def create_session(
        self,
        ontology_id: str,
        extraction_type: str,
        input_data: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """Create a new extraction session record.

        Args:
            ontology_id: Associated ontology ID.
            extraction_type: One of 'natural_language', 'document', 'knowledge_base'.
            input_data: Optional input metadata dict.

        Returns:
            {"status": "ok", "session_id": "..."}
        """
        session_id = str(uuid.uuid4())
        now = datetime.now().isoformat()
        conn = self._get_conn()
        try:
            conn.execute(
                """INSERT INTO extraction_sessions
                   (session_id, ontology_id, extraction_type, input_data, result_data,
                    status, conflicts, channel_b_status, created_at, updated_at)
                   VALUES (?, ?, ?, ?, NULL, 'pending', NULL, NULL, ?, ?)""",
                (
                    session_id,
                    ontology_id,
                    extraction_type,
                    self._serialize_json(input_data) if input_data else None,
                    now,
                    now,
                ),
            )
            conn.commit()
        finally:
            conn.close()
        return {"status": "ok", "session_id": session_id}

    def update_session(
        self,
        session_id: str,
        updates: Dict[str, Any],
    ) -> Dict[str, Any]:
        """Update an extraction session with new fields.

        Supported keys in `updates`:
            status, result_data, conflicts, channel_b_status

        Returns:
            {"status": "ok"} or {"status": "error", "message": "..."}
        """
        if not updates:
            return {"status": "ok"}
        allowed = ("status", "result_data", "conflicts", "channel_b_status")
        sets = []
        params: List[Any] = []
        for key in allowed:
            if key in updates:
                sets.append(f"{key} = ?")
                val = updates[key]
                if isinstance(val, (dict, list)):
                    val = self._serialize_json(val)
                params.append(val)
        if not sets:
            return {"status": "ok"}
        sets.append("updated_at = ?")
        params.append(datetime.now().isoformat())
        params.append(session_id)

        conn = self._get_conn()
        try:
            conn.execute(
                f"UPDATE extraction_sessions SET {', '.join(sets)} WHERE session_id = ?",
                params,
            )
            conn.commit()
        finally:
            conn.close()
        return {"status": "ok"}

    def get_session(self, session_id: str) -> Optional[Dict[str, Any]]:
        """Retrieve a session by ID.

        Returns:
            Dict with session fields, or None if not found. JSON fields
            (input_data, result_data, conflicts) are deserialized.
        """
        conn = self._get_conn()
        conn.row_factory = sqlite3.Row
        try:
            row = conn.execute(
                "SELECT * FROM extraction_sessions WHERE session_id = ?",
                (session_id,),
            ).fetchone()
        finally:
            conn.close()
        if not row:
            return None
        result = dict(row)
        for key in ("input_data", "result_data", "conflicts"):
            if result.get(key):
                result[key] = self._deserialize_json(result[key])
        return result
