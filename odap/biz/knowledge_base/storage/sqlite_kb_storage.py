import sqlite3
import json
import os
import uuid
from datetime import datetime, timezone
from typing import Dict, Any, List, Optional

DEFAULT_DB_DIR = os.environ.get("DATA_DIR", os.path.join(os.getcwd(), "data"))
DEFAULT_DB_PATH = os.path.join(DEFAULT_DB_DIR, "knowledge_bases.db")


class SQLiteKnowledgeBaseStorage:
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
        c = conn.cursor()
        c.execute('''CREATE TABLE IF NOT EXISTS knowledge_bases (
            kb_id TEXT PRIMARY KEY,
            name TEXT NOT NULL,
            description TEXT DEFAULT '',
            knowledge_count INTEGER DEFAULT 0,
            category_count INTEGER DEFAULT 0,
            created_by TEXT DEFAULT 'system',
            status TEXT DEFAULT 'active',
            created_at TEXT NOT NULL,
            updated_at TEXT NOT NULL
        )''')
        c.execute('''CREATE TABLE IF NOT EXISTS kb_categories (
            category_id TEXT PRIMARY KEY,
            kb_id TEXT NOT NULL,
            name TEXT NOT NULL,
            parent_id TEXT,
            document_count INTEGER DEFAULT 0,
            updated_at TEXT NOT NULL,
            FOREIGN KEY (kb_id) REFERENCES knowledge_bases(kb_id)
        )''')
        c.execute('''CREATE TABLE IF NOT EXISTS kb_documents (
            doc_id TEXT PRIMARY KEY,
            kb_id TEXT NOT NULL,
            category_id TEXT,
            title TEXT NOT NULL,
            content_type TEXT DEFAULT 'text',
            file_type TEXT,
            file_size INTEGER,
            file_url TEXT,
            content TEXT,
            keywords TEXT DEFAULT '[]',
            summary TEXT,
            status TEXT DEFAULT 'pending',
            graph_built INTEGER DEFAULT 0,
            created_at TEXT NOT NULL,
            updated_at TEXT NOT NULL,
            FOREIGN KEY (kb_id) REFERENCES knowledge_bases(kb_id)
        )''')
        conn.commit()
        conn.close()

    def _row_to_dict(self, row: sqlite3.Row) -> Dict[str, Any]:
        d = dict(row)
        if 'keywords' in d and isinstance(d['keywords'], str):
            try:
                d['keywords'] = json.loads(d['keywords'])
            except (json.JSONDecodeError, TypeError):
                d['keywords'] = []
        if 'graph_built' in d:
            d['graph_built'] = bool(d['graph_built'])
        return d

    # Knowledge Base CRUD
    def list_knowledge_bases(self) -> List[Dict[str, Any]]:
        conn = self._get_conn()
        try:
            rows = conn.execute("SELECT * FROM knowledge_bases ORDER BY created_at DESC").fetchall()
            return [self._row_to_dict(r) for r in rows]
        finally:
            conn.close()

    def get_knowledge_base(self, kb_id: str) -> Optional[Dict[str, Any]]:
        conn = self._get_conn()
        try:
            row = conn.execute("SELECT * FROM knowledge_bases WHERE kb_id = ?", (kb_id,)).fetchone()
            if not row:
                return None
            return self._row_to_dict(row)
        finally:
            conn.close()

    def create_knowledge_base(self, data: Dict[str, Any]) -> Dict[str, Any]:
        now = datetime.now(timezone.utc).isoformat()
        kb_id = f"kb_{uuid.uuid4().hex[:12]}"
        record = {
            'kb_id': kb_id,
            'name': data.get('name', ''),
            'description': data.get('description', ''),
            'knowledge_count': 0,
            'category_count': 0,
            'created_by': data.get('created_by', 'system'),
            'status': 'active',
            'created_at': now,
            'updated_at': now,
        }
        conn = self._get_conn()
        try:
            cols = ', '.join(record.keys())
            placeholders = ', '.join(['?'] * len(record))
            conn.execute(f"INSERT INTO knowledge_bases ({cols}) VALUES ({placeholders})", list(record.values()))
            conn.commit()
            return self.get_knowledge_base(kb_id)
        finally:
            conn.close()

    def update_knowledge_base(self, kb_id: str, data: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        existing = self.get_knowledge_base(kb_id)
        if not existing:
            return None
        now = datetime.now(timezone.utc).isoformat()
        sets = []
        values = []
        for key, val in data.items():
            if key in ('kb_id', 'created_at', 'created_by'):
                continue
            if val is not None:
                sets.append(f"{key} = ?")
                values.append(val)
        sets.append("updated_at = ?")
        values.append(now)
        values.append(kb_id)
        conn = self._get_conn()
        try:
            conn.execute(f"UPDATE knowledge_bases SET {', '.join(sets)} WHERE kb_id = ?", values)
            conn.commit()
            return self.get_knowledge_base(kb_id)
        finally:
            conn.close()

    def delete_knowledge_base(self, kb_id: str) -> bool:
        existing = self.get_knowledge_base(kb_id)
        if not existing:
            return False
        conn = self._get_conn()
        try:
            conn.execute("DELETE FROM kb_documents WHERE kb_id = ?", (kb_id,))
            conn.execute("DELETE FROM kb_categories WHERE kb_id = ?", (kb_id,))
            conn.execute("DELETE FROM knowledge_bases WHERE kb_id = ?", (kb_id,))
            conn.commit()
            return True
        finally:
            conn.close()

    # Category CRUD
    def list_categories(self, kb_id: str) -> List[Dict[str, Any]]:
        conn = self._get_conn()
        try:
            rows = conn.execute("SELECT * FROM kb_categories WHERE kb_id = ? ORDER BY name", (kb_id,)).fetchall()
            return [self._row_to_dict(r) for r in rows]
        finally:
            conn.close()

    def create_category(self, kb_id: str, data: Dict[str, Any]) -> Dict[str, Any]:
        now = datetime.now(timezone.utc).isoformat()
        category_id = f"cat_{uuid.uuid4().hex[:12]}"
        record = {
            'category_id': category_id,
            'kb_id': kb_id,
            'name': data.get('name', ''),
            'parent_id': data.get('parent_id'),
            'document_count': 0,
            'updated_at': now,
        }
        conn = self._get_conn()
        try:
            cols = ', '.join(record.keys())
            placeholders = ', '.join(['?'] * len(record))
            conn.execute(f"INSERT INTO kb_categories ({cols}) VALUES ({placeholders})", list(record.values()))
            conn.execute("UPDATE knowledge_bases SET category_count = category_count + 1, updated_at = ? WHERE kb_id = ?", (now, kb_id))
            conn.commit()
            return dict(record)
        finally:
            conn.close()

    def delete_category(self, kb_id: str, category_id: str) -> bool:
        conn = self._get_conn()
        try:
            row = conn.execute("SELECT * FROM kb_categories WHERE category_id = ? AND kb_id = ?", (category_id, kb_id)).fetchone()
            if not row:
                return False
            now = datetime.now(timezone.utc).isoformat()
            conn.execute("DELETE FROM kb_categories WHERE category_id = ? AND kb_id = ?", (category_id, kb_id))
            conn.execute("UPDATE knowledge_bases SET category_count = category_count - 1, updated_at = ? WHERE kb_id = ?", (now, kb_id))
            conn.commit()
            return True
        finally:
            conn.close()

    # Document CRUD
    def list_documents(self, kb_id: str, category_id: Optional[str] = None) -> List[Dict[str, Any]]:
        conn = self._get_conn()
        try:
            if category_id:
                rows = conn.execute("SELECT * FROM kb_documents WHERE kb_id = ? AND category_id = ? ORDER BY created_at DESC", (kb_id, category_id)).fetchall()
            else:
                rows = conn.execute("SELECT * FROM kb_documents WHERE kb_id = ? ORDER BY created_at DESC", (kb_id,)).fetchall()
            return [self._row_to_dict(r) for r in rows]
        finally:
            conn.close()

    def create_document(self, kb_id: str, data: Dict[str, Any]) -> Dict[str, Any]:
        now = datetime.now(timezone.utc).isoformat()
        doc_id = f"doc_{uuid.uuid4().hex[:12]}"
        record = {
            'doc_id': doc_id,
            'kb_id': kb_id,
            'category_id': data.get('category_id'),
            'title': data.get('title', ''),
            'content_type': data.get('content_type', 'text'),
            'file_type': data.get('file_type'),
            'file_size': data.get('file_size'),
            'file_url': data.get('file_url'),
            'content': data.get('content'),
            'keywords': json.dumps(data.get('keywords', []), ensure_ascii=False),
            'summary': data.get('summary'),
            'status': 'pending',
            'graph_built': 0,
            'created_at': now,
            'updated_at': now,
        }
        conn = self._get_conn()
        try:
            cols = ', '.join(record.keys())
            placeholders = ', '.join(['?'] * len(record))
            conn.execute(f"INSERT INTO kb_documents ({cols}) VALUES ({placeholders})", list(record.values()))
            conn.execute("UPDATE knowledge_bases SET knowledge_count = knowledge_count + 1, updated_at = ? WHERE kb_id = ?", (now, kb_id))
            conn.commit()
            return self._row_to_dict(conn.execute("SELECT * FROM kb_documents WHERE doc_id = ?", (doc_id,)).fetchone())
        finally:
            conn.close()

    def get_document(self, kb_id: str, doc_id: str) -> Optional[Dict[str, Any]]:
        conn = self._get_conn()
        try:
            row = conn.execute("SELECT * FROM kb_documents WHERE doc_id = ? AND kb_id = ?", (doc_id, kb_id)).fetchone()
            if not row:
                return None
            return self._row_to_dict(row)
        finally:
            conn.close()

    def delete_document(self, kb_id: str, doc_id: str) -> bool:
        conn = self._get_conn()
        try:
            row = conn.execute("SELECT * FROM kb_documents WHERE doc_id = ? AND kb_id = ?", (doc_id, kb_id)).fetchone()
            if not row:
                return False
            now = datetime.now(timezone.utc).isoformat()
            conn.execute("DELETE FROM kb_documents WHERE doc_id = ? AND kb_id = ?", (doc_id, kb_id))
            conn.execute("UPDATE knowledge_bases SET knowledge_count = knowledge_count - 1, updated_at = ? WHERE kb_id = ?", (now, kb_id))
            conn.commit()
            return True
        finally:
            conn.close()
