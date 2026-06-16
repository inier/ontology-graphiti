"""
SQLite Conflict Storage

冲突记录 SQLite 持久化
- 每次操作 connect/close（无连接池，符合 AGENTS.md 规则 8）
- 复杂字段 Dict/List → JSON TEXT 列
- Enum → .value 字符串
- datetime → ISO 字符串
"""
from __future__ import annotations

import json
import os
import sqlite3
from datetime import datetime
from typing import Any, Dict, List, Optional


class SQLiteConflictStorage:
    """冲突记录 SQLite 持久化"""

    def __init__(self, db_path: str = None):
        self.db_path = db_path or os.path.join(
            os.environ.get("DATA_DIR", os.path.join(os.getcwd(), "data")),
            "conflict_records.db",
        )
        self._init_db()

    def _init_db(self) -> None:
        """初始化 conflict_records 表 + 索引"""
        os.makedirs(os.path.dirname(self.db_path), exist_ok=True)
        conn = sqlite3.connect(self.db_path)
        try:
            conn.execute("""
                CREATE TABLE IF NOT EXISTS conflict_records (
                    id TEXT PRIMARY KEY,
                    entity_id TEXT NOT NULL,
                    entity_type TEXT DEFAULT 'unknown',
                    field_name TEXT NOT NULL,
                    conflict_type TEXT NOT NULL,
                    candidates TEXT,
                    status TEXT NOT NULL DEFAULT 'pending',
                    strategy TEXT,
                    chosen TEXT,
                    detected_at TEXT NOT NULL,
                    resolved_at TEXT,
                    resolver_id TEXT,
                    notes TEXT DEFAULT ''
                )
            """)
            conn.execute(
                "CREATE INDEX IF NOT EXISTS idx_conflict_status "
                "ON conflict_records(status)"
            )
            conn.execute(
                "CREATE INDEX IF NOT EXISTS idx_conflict_entity "
                "ON conflict_records(entity_id)"
            )
            conn.commit()
        finally:
            conn.close()

    # ---------- helpers ----------

    @staticmethod
    def _iso(dt: Optional[datetime]) -> Optional[str]:
        if dt is None:
            return None
        if isinstance(dt, str):
            return dt
        return dt.isoformat()

    @staticmethod
    def _parse_dt(s: Optional[str]) -> Optional[datetime]:
        if not s:
            return None
        try:
            return datetime.fromisoformat(s)
        except (ValueError, TypeError):
            return None

    @staticmethod
    def _load_json(raw: Optional[str], default: Any) -> Any:
        if not raw:
            return default
        try:
            return json.loads(raw)
        except (ValueError, TypeError):
            return default

    def _row_to_dict(self, row: sqlite3.Row) -> Dict[str, Any]:
        """将数据库行转换为 dict，反序列化 JSON 字段"""
        return {
            "id": row["id"],
            "entity_id": row["entity_id"],
            "entity_type": row["entity_type"] or "unknown",
            "field_name": row["field_name"],
            "conflict_type": row["conflict_type"],
            "candidates": self._load_json(row["candidates"], []),
            "status": row["status"],
            "strategy": row["strategy"],
            "chosen": self._load_json(row["chosen"], None),
            "detected_at": row["detected_at"],
            "resolved_at": row["resolved_at"],
            "resolver_id": row["resolver_id"],
            "notes": row["notes"] or "",
        }

    # ---------- CRUD ----------

    def save_conflict(self, record: Dict[str, Any]) -> str:
        """保存冲突记录 (INSERT OR REPLACE)，返回 conflict_id"""
        conflict_id = record.get("id", "")
        candidates_json = json.dumps(
            record.get("candidates", []), ensure_ascii=False, default=str
        )
        chosen_raw = record.get("chosen")
        chosen_json = json.dumps(chosen_raw, ensure_ascii=False, default=str) if chosen_raw else None

        conn = sqlite3.connect(self.db_path)
        try:
            conn.execute(
                """
                INSERT OR REPLACE INTO conflict_records (
                    id, entity_id, entity_type, field_name, conflict_type,
                    candidates, status, strategy, chosen,
                    detected_at, resolved_at, resolver_id, notes
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    conflict_id,
                    record.get("entity_id", ""),
                    record.get("entity_type", "unknown"),
                    record.get("field_name", ""),
                    record.get("conflict_type", "value_mismatch"),
                    candidates_json,
                    record.get("status", "pending"),
                    record.get("strategy"),
                    chosen_json,
                    record.get("detected_at") or self._iso(datetime.now()),
                    record.get("resolved_at"),
                    record.get("resolver_id"),
                    record.get("notes", ""),
                ),
            )
            conn.commit()
        finally:
            conn.close()
        return conflict_id

    def get_conflict(self, conflict_id: str) -> Optional[Dict[str, Any]]:
        """获取单条冲突记录"""
        conn = sqlite3.connect(self.db_path)
        try:
            conn.row_factory = sqlite3.Row
            row = conn.execute(
                "SELECT * FROM conflict_records WHERE id = ?", (conflict_id,)
            ).fetchone()
        finally:
            conn.close()
        return self._row_to_dict(row) if row else None

    def list_conflicts(
        self,
        status: Optional[str] = None,
        limit: int = 100,
        offset: int = 0,
    ) -> List[Dict[str, Any]]:
        """列出冲突记录，可选按 status 过滤"""
        sql = "SELECT * FROM conflict_records WHERE 1=1"
        params: List[Any] = []
        if status:
            sql += " AND status = ?"
            params.append(status)
        sql += " ORDER BY detected_at DESC LIMIT ? OFFSET ?"
        params.extend([limit, offset])

        conn = sqlite3.connect(self.db_path)
        try:
            conn.row_factory = sqlite3.Row
            rows = conn.execute(sql, params).fetchall()
        finally:
            conn.close()
        return [self._row_to_dict(r) for r in rows]

    def update_conflict(self, conflict_id: str, updates: Dict[str, Any]) -> bool:
        """更新冲突记录的部分字段，返回是否成功"""
        if not updates:
            return False

        set_clauses: List[str] = []
        params: List[Any] = []

        allowed_fields = {
            "entity_id", "entity_type", "field_name", "conflict_type",
            "candidates", "status", "strategy", "chosen",
            "resolved_at", "resolver_id", "notes",
        }

        for key, value in updates.items():
            if key not in allowed_fields:
                continue
            if key == "candidates":
                set_clauses.append("candidates = ?")
                params.append(json.dumps(value, ensure_ascii=False, default=str))
            elif key == "chosen":
                set_clauses.append("chosen = ?")
                params.append(
                    json.dumps(value, ensure_ascii=False, default=str) if value else None
                )
            else:
                set_clauses.append(f"{key} = ?")
                params.append(value)

        if not set_clauses:
            return False

        params.append(conflict_id)
        sql = f"UPDATE conflict_records SET {', '.join(set_clauses)} WHERE id = ?"

        conn = sqlite3.connect(self.db_path)
        try:
            cur = conn.execute(sql, params)
            conn.commit()
            updated = cur.rowcount > 0
        finally:
            conn.close()
        return updated

    def delete_conflict(self, conflict_id: str) -> bool:
        """删除冲突记录，返回是否成功"""
        conn = sqlite3.connect(self.db_path)
        try:
            cur = conn.execute(
                "DELETE FROM conflict_records WHERE id = ?", (conflict_id,)
            )
            conn.commit()
            deleted = cur.rowcount > 0
        finally:
            conn.close()
        return deleted

    def count_conflicts(self, status: Optional[str] = None) -> int:
        """统计冲突记录数，可选按 status 过滤"""
        sql = "SELECT COUNT(*) FROM conflict_records WHERE 1=1"
        params: List[Any] = []
        if status:
            sql += " AND status = ?"
            params.append(status)

        conn = sqlite3.connect(self.db_path)
        try:
            row = conn.execute(sql, params).fetchone()
        finally:
            conn.close()
        return row[0] if row else 0
