import json
import os
import uuid
import logging
import sqlite3
from datetime import datetime, timezone
from typing import Dict, List, Any, Optional

from pydantic import BaseModel, Field

from .context_window import ContextWindow, ChatMessage, MessageRole
from .cot_builder import CoTTree

logger = logging.getLogger(__name__)


class Session(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4())[:12])
    workspace_id: str = "default"
    title: str = ""
    messages: List[ChatMessage] = Field(default_factory=list)
    context_window: ContextWindow = Field(default_factory=ContextWindow)
    cot_tree_data: Dict[str, Any] = Field(default_factory=dict)
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    updated_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    is_active: bool = True
    needs_compaction: bool = False


class SessionSummary(BaseModel):
    id: str
    workspace_id: str
    title: str
    message_count: int
    created_at: datetime
    updated_at: datetime
    is_active: bool


class SessionStore:
    def __init__(self, db_path: Optional[str] = None):
        # 默认写入 DATA_DIR/sessions.db，避免污染项目根目录（规则 13）
        if db_path is None:
            data_dir = os.environ.get(
                'DATA_DIR',
                os.path.join(os.getcwd(), 'apps', 'api', 'data'),
            )
            db_path = os.path.join(data_dir, 'sessions.db')
        self.db_path = db_path
        self._init_db()

    def _init_db(self):
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS sessions (
                id TEXT PRIMARY KEY,
                workspace_id TEXT NOT NULL,
                title TEXT NOT NULL DEFAULT '',
                messages TEXT NOT NULL DEFAULT '[]',
                context_window TEXT NOT NULL DEFAULT '{}',
                cot_tree_data TEXT NOT NULL DEFAULT '{}',
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL,
                is_active INTEGER NOT NULL DEFAULT 1,
                needs_compaction INTEGER NOT NULL DEFAULT 0
            )
        ''')
        cursor.execute('CREATE INDEX IF NOT EXISTS idx_sessions_workspace ON sessions(workspace_id)')
        cursor.execute('CREATE INDEX IF NOT EXISTS idx_sessions_active ON sessions(is_active)')
        self._migrate_add_needs_compaction(cursor)
        conn.commit()
        conn.close()

    def _migrate_add_needs_compaction(self, cursor):
        """为旧表添加 needs_compaction 列"""
        try:
            cursor.execute("SELECT needs_compaction FROM sessions LIMIT 1")
        except sqlite3.OperationalError:
            cursor.execute("ALTER TABLE sessions ADD COLUMN needs_compaction INTEGER NOT NULL DEFAULT 0")

    def save_session(self, session: Session) -> str:
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        cursor.execute('''
            INSERT OR REPLACE INTO sessions
            (id, workspace_id, title, messages, context_window, cot_tree_data, created_at, updated_at, is_active, needs_compaction)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        ''', (
            session.id,
            session.workspace_id,
            session.title,
            json.dumps([m.model_dump() for m in session.messages], default=str, ensure_ascii=False),
            json.dumps(session.context_window.model_dump(), default=str, ensure_ascii=False),
            json.dumps(session.cot_tree_data, default=str, ensure_ascii=False),
            session.created_at.isoformat(),
            datetime.now(timezone.utc).isoformat(),
            1 if session.is_active else 0,
            1 if session.needs_compaction else 0,
        ))
        conn.commit()
        conn.close()
        return session.id

    def load_session(self, session_id: str) -> Optional[Session]:
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        cursor.execute('SELECT * FROM sessions WHERE id = ?', (session_id,))
        row = cursor.fetchone()
        conn.close()

        if not row:
            return None

        return self._row_to_session(row)

    def list_sessions(self, workspace_id: str, limit: int = 20) -> List[SessionSummary]:
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        cursor.execute('''
            SELECT id, workspace_id, title, messages, created_at, updated_at, is_active
            FROM sessions WHERE workspace_id = ? AND is_active = 1
            ORDER BY updated_at DESC LIMIT ?
        ''', (workspace_id, limit))
        rows = cursor.fetchall()
        conn.close()

        summaries = []
        for row in rows:
            messages = json.loads(row[3]) if row[3] else []
            summaries.append(SessionSummary(
                id=row[0],
                workspace_id=row[1],
                title=row[2],
                message_count=len(messages),
                created_at=datetime.fromisoformat(row[4]),
                updated_at=datetime.fromisoformat(row[5]),
                is_active=bool(row[6]),
            ))
        return summaries

    def delete_session(self, session_id: str) -> bool:
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        cursor.execute('UPDATE sessions SET is_active = 0, updated_at = ? WHERE id = ?',
                       (datetime.now(timezone.utc).isoformat(), session_id))
        affected = cursor.rowcount
        conn.commit()
        conn.close()
        return affected > 0

    def _row_to_session(self, row) -> Session:
        messages_data = json.loads(row[3]) if row[3] else []
        messages = [ChatMessage(**m) for m in messages_data]
        cw_data = json.loads(row[4]) if row[4] else {}
        context_window = ContextWindow(**cw_data)
        cot_data = json.loads(row[5]) if row[5] else {}

        needs_compaction = bool(row[9]) if len(row) > 9 else False

        return Session(
            id=row[0],
            workspace_id=row[1],
            title=row[2],
            messages=messages,
            context_window=context_window,
            cot_tree_data=cot_data,
            created_at=datetime.fromisoformat(row[6]),
            updated_at=datetime.fromisoformat(row[7]),
            is_active=bool(row[8]),
            needs_compaction=needs_compaction,
        )
