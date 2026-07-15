import sqlite3
import json
import os
from typing import Dict, Any, List, Optional
from datetime import datetime
from ..models import MemoryEntry, MemoryType, MemoryStatus, MemoryConsolidation

DEFAULT_DB_DIR = os.environ.get("DATA_DIR", os.path.join(os.getcwd(), "data"))
DEFAULT_DB_PATH = os.path.join(DEFAULT_DB_DIR, "ontology_session.db")


class SQLiteOntologyMemoryStorage:
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
            CREATE TABLE IF NOT EXISTS memory_entries (
                memory_id TEXT PRIMARY KEY,
                memory_type TEXT NOT NULL,
                content TEXT NOT NULL,
                summary TEXT,
                keywords TEXT,
                entities TEXT,
                source_scenario_id TEXT,
                source_session_id TEXT,
                importance REAL DEFAULT 0.5,
                access_count INTEGER DEFAULT 0,
                decay_factor REAL DEFAULT 1.0,
                embedding TEXT,
                created_at TEXT NOT NULL,
                last_accessed_at TEXT NOT NULL,
                expires_at TEXT,
                status TEXT NOT NULL DEFAULT 'active',
                metadata TEXT
            )
        ''')
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS memory_consolidations (
                consolidation_id TEXT PRIMARY KEY,
                source_ids TEXT NOT NULL,
                result_id TEXT,
                strategy TEXT NOT NULL DEFAULT 'merge',
                summary TEXT,
                importance REAL DEFAULT 0.5,
                created_at TEXT NOT NULL
            )
        ''')
        conn.commit()
        conn.close()

    def _serialize_json(self, data: Any) -> str:
        return json.dumps(data, ensure_ascii=False)

    def _deserialize_json(self, data: str) -> Any:
        if not data:
            return None
        try:
            return json.loads(data)
        except (json.JSONDecodeError, TypeError, ValueError):
            return None

    def save_memory(self, entry: MemoryEntry) -> None:
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        data = entry.model_dump()
        embedding_data = self._serialize_json(data.get('embedding')) if data.get('embedding') else None
        cursor.execute('''
            INSERT OR REPLACE INTO memory_entries
            (memory_id, memory_type, content, summary, keywords, entities,
             source_scenario_id, source_session_id, importance, access_count,
             decay_factor, embedding, created_at, last_accessed_at, expires_at,
             status, metadata)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        ''', (
            data['memory_id'],
            data['memory_type'].value,
            data['content'],
            data.get('summary'),
            self._serialize_json(data.get('keywords', [])),
            self._serialize_json(data.get('entities', [])),
            data.get('source_scenario_id'),
            data.get('source_session_id'),
            data.get('importance', 0.5),
            data.get('access_count', 0),
            data.get('decay_factor', 1.0),
            embedding_data,
            data['created_at'].isoformat(),
            data['last_accessed_at'].isoformat(),
            data.get('expires_at'),
            data['status'].value,
            self._serialize_json(data.get('metadata', {}))
        ))
        conn.commit()
        conn.close()

    def get_memory(self, memory_id: str) -> Optional[MemoryEntry]:
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        cursor.execute('SELECT * FROM memory_entries WHERE memory_id = ?', (memory_id,))
        row = cursor.fetchone()
        conn.close()
        if not row:
            return None
        return self._row_to_memory_entry(row)

    def list_memories(self, filters: Dict[str, Any] = None,
                      page: int = 1, page_size: int = 10) -> List[MemoryEntry]:
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        query = 'SELECT * FROM memory_entries'
        params = []
        if filters:
            where_clauses = []
            for key, value in filters.items():
                if key in ('memory_type', 'status', 'source_scenario_id', 'source_session_id'):
                    where_clauses.append(f"{key} = ?")
                    params.append(value if not isinstance(value, (MemoryType, MemoryStatus)) else value.value)
            if where_clauses:
                query += ' WHERE ' + ' AND '.join(where_clauses)
        query += ' ORDER BY created_at DESC LIMIT ? OFFSET ?'
        params.extend([page_size, (page - 1) * page_size])
        cursor.execute(query, params)
        rows = cursor.fetchall()
        conn.close()
        return [self._row_to_memory_entry(row) for row in rows]

    def delete_memory(self, memory_id: str) -> bool:
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        cursor.execute('DELETE FROM memory_entries WHERE memory_id = ?', (memory_id,))
        affected = cursor.rowcount
        conn.commit()
        conn.close()
        return affected > 0

    def update_memory_access(self, memory_id: str) -> None:
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        now = datetime.now().isoformat()
        cursor.execute('''
            UPDATE memory_entries SET access_count = access_count + 1,
            last_accessed_at = ? WHERE memory_id = ?
        ''', (now, memory_id))
        conn.commit()
        conn.close()

    def update_memory(self, memory_id: str, updates: Dict[str, Any]) -> None:
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        set_clause = []
        params = []
        json_keys = {'keywords', 'entities', 'embedding', 'metadata'}
        enum_keys = {'memory_type': MemoryType, 'status': MemoryStatus}
        for key, value in updates.items():
            if key == 'memory_id':
                continue
            if key in enum_keys and isinstance(value, enum_keys[key]):
                value = value.value
            if key in json_keys:
                value = self._serialize_json(value)
            set_clause.append(f"{key} = ?")
            params.append(value)
        if set_clause:
            params.append(memory_id)
            query = f"UPDATE memory_entries SET {', '.join(set_clause)} WHERE memory_id = ?"
            cursor.execute(query, params)
        conn.commit()
        conn.close()

    def save_consolidation(self, consolidation: MemoryConsolidation) -> None:
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        data = consolidation.model_dump()
        cursor.execute('''
            INSERT OR REPLACE INTO memory_consolidations
            (consolidation_id, source_ids, result_id, strategy, summary, importance, created_at)
            VALUES (?, ?, ?, ?, ?, ?, ?)
        ''', (
            data['consolidation_id'],
            self._serialize_json(data.get('source_ids', [])),
            data.get('result_id'),
            data.get('strategy', 'merge'),
            data.get('summary', ''),
            data.get('importance', 0.5),
            data['created_at'].isoformat()
        ))
        conn.commit()
        conn.close()

    def list_consolidations(self, page: int = 1, page_size: int = 10) -> List[MemoryConsolidation]:
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        cursor.execute(
            'SELECT * FROM memory_consolidations ORDER BY created_at DESC LIMIT ? OFFSET ?',
            (page_size, (page - 1) * page_size)
        )
        rows = cursor.fetchall()
        conn.close()
        return [self._row_to_consolidation(row) for row in rows]

    def count_memories(self, filters: Dict[str, Any] = None) -> int:
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        query = 'SELECT COUNT(*) FROM memory_entries'
        params = []
        if filters:
            where_clauses = []
            for key, value in filters.items():
                if key in ('memory_type', 'status', 'source_scenario_id'):
                    where_clauses.append(f"{key} = ?")
                    params.append(value if not isinstance(value, (MemoryType, MemoryStatus)) else value.value)
            if where_clauses:
                query += ' WHERE ' + ' AND '.join(where_clauses)
        cursor.execute(query, params)
        count = cursor.fetchone()[0]
        conn.close()
        return count

    def _row_to_memory_entry(self, row) -> MemoryEntry:
        return MemoryEntry(
            memory_id=row['memory_id'],
            memory_type=MemoryType(row['memory_type']),
            content=row['content'],
            summary=row['summary'],
            keywords=self._deserialize_json(row['keywords']) or [],
            entities=self._deserialize_json(row['entities']) or [],
            source_scenario_id=row['source_scenario_id'],
            source_session_id=row['source_session_id'],
            importance=row['importance'],
            access_count=row['access_count'],
            decay_factor=row['decay_factor'],
            embedding=self._deserialize_json(row['embedding']) if row['embedding'] else None,
            created_at=datetime.fromisoformat(row['created_at']),
            last_accessed_at=datetime.fromisoformat(row['last_accessed_at']),
            expires_at=row['expires_at'],
            status=MemoryStatus(row['status']),
            metadata=self._deserialize_json(row['metadata']) or {}
        )

    def _row_to_consolidation(self, row) -> MemoryConsolidation:
        return MemoryConsolidation(
            consolidation_id=row['consolidation_id'],
            source_ids=self._deserialize_json(row['source_ids']) or [],
            result_id=row['result_id'],
            strategy=row['strategy'],
            summary=row['summary'],
            importance=row['importance'],
            created_at=datetime.fromisoformat(row['created_at'])
        )
