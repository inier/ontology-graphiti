"""
SQLite Branch Storage (T353)

3 张表：branches / merge_requests / conflicts
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

from ..models import (
    Branch,
    BranchStatus,
    Conflict,
    ConflictResolution,
    MergeRequest,
    MergeRequestStatus,
)


class SQLiteBranchStorage:
    """分支 / 合并请求 / 冲突 SQLite 持久化"""

    def __init__(self, db_path: str = None):
        self.db_path = db_path or os.path.join(
            os.environ.get("DATA_DIR", os.path.join(os.getcwd(), "data")),
            "ontology_branch.db",
        )
        self._init_db()

    def _init_db(self) -> None:
        """初始化 3 张表 + 索引"""
        os.makedirs(os.path.dirname(self.db_path), exist_ok=True)
        conn = sqlite3.connect(self.db_path)
        try:
            self._init_branches(conn)
            self._init_merge_requests(conn)
            self._init_conflicts(conn)
            conn.commit()
        finally:
            conn.close()

    @staticmethod
    def _init_branches(conn: sqlite3.Connection) -> None:
        """初始化 branches 表 + 索引"""
        conn.execute("""
            CREATE TABLE IF NOT EXISTS branches (
                id TEXT PRIMARY KEY,
                name TEXT NOT NULL,
                ontology_id TEXT NOT NULL,
                base_version_id TEXT NOT NULL,
                head_version_id TEXT NOT NULL,
                status TEXT NOT NULL DEFAULT 'active',
                description TEXT DEFAULT '',
                created_by TEXT DEFAULT 'system',
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL,
                merged_at TEXT,
                merge_target_branch_id TEXT
            )
        """)
        conn.execute(
            "CREATE INDEX IF NOT EXISTS idx_branches_ontology "
            "ON branches(ontology_id)"
        )
        conn.execute(
            "CREATE INDEX IF NOT EXISTS idx_branches_status "
            "ON branches(status)"
        )

    @staticmethod
    def _init_merge_requests(conn: sqlite3.Connection) -> None:
        """初始化 merge_requests 表 + 索引"""
        conn.execute("""
            CREATE TABLE IF NOT EXISTS merge_requests (
                id TEXT PRIMARY KEY,
                source_branch_id TEXT NOT NULL,
                target_branch_id TEXT NOT NULL,
                title TEXT NOT NULL,
                description TEXT DEFAULT '',
                conflicts TEXT DEFAULT '[]',
                status TEXT NOT NULL DEFAULT 'open',
                base_snapshot TEXT DEFAULT '{}',
                ours_snapshot TEXT DEFAULT '{}',
                theirs_snapshot TEXT DEFAULT '{}',
                created_by TEXT DEFAULT 'system',
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL,
                merged_at TEXT
            )
        """)
        conn.execute(
            "CREATE INDEX IF NOT EXISTS idx_mr_source "
            "ON merge_requests(source_branch_id)"
        )
        conn.execute(
            "CREATE INDEX IF NOT EXISTS idx_mr_target "
            "ON merge_requests(target_branch_id)"
        )
        conn.execute(
            "CREATE INDEX IF NOT EXISTS idx_mr_status "
            "ON merge_requests(status)"
        )

    @staticmethod
    def _init_conflicts(conn: sqlite3.Connection) -> None:
        """初始化 conflicts 表 + 索引"""
        conn.execute("""
            CREATE TABLE IF NOT EXISTS conflicts (
                id TEXT PRIMARY KEY,
                merge_request_id TEXT NOT NULL,
                path TEXT NOT NULL,
                base_value TEXT,
                ours_value TEXT,
                theirs_value TEXT,
                resolution TEXT NOT NULL DEFAULT 'unresolved',
                resolved_value TEXT,
                resolved_by TEXT DEFAULT '',
                resolved_at TEXT
            )
        """)
        conn.execute(
            "CREATE INDEX IF NOT EXISTS idx_conflicts_mr "
            "ON conflicts(merge_request_id)"
        )

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
    def _load_json(raw: Optional[str], default):
        if not raw:
            return default
        try:
            return json.loads(raw)
        except (ValueError, TypeError):
            return default

    def _row_to_branch(self, row: sqlite3.Row) -> Branch:
        return Branch(
            id=row["id"],
            name=row["name"],
            ontology_id=row["ontology_id"],
            base_version_id=row["base_version_id"],
            head_version_id=row["head_version_id"],
            status=BranchStatus(row["status"]),
            description=row["description"] or "",
            created_by=row["created_by"] or "system",
            created_at=self._parse_dt(row["created_at"]) or datetime.now(),
            updated_at=self._parse_dt(row["updated_at"]) or datetime.now(),
            merged_at=self._parse_dt(row["merged_at"]),
            merge_target_branch_id=row["merge_target_branch_id"],
        )

    def _row_to_mr(self, row: sqlite3.Row) -> MergeRequest:
        return MergeRequest(
            id=row["id"],
            source_branch_id=row["source_branch_id"],
            target_branch_id=row["target_branch_id"],
            title=row["title"],
            description=row["description"] or "",
            conflicts=self._load_json(row["conflicts"], []),
            status=MergeRequestStatus(row["status"]),
            base_snapshot=self._load_json(row["base_snapshot"], {}),
            ours_snapshot=self._load_json(row["ours_snapshot"], {}),
            theirs_snapshot=self._load_json(row["theirs_snapshot"], {}),
            created_by=row["created_by"] or "system",
            created_at=self._parse_dt(row["created_at"]) or datetime.now(),
            updated_at=self._parse_dt(row["updated_at"]) or datetime.now(),
            merged_at=self._parse_dt(row["merged_at"]),
        )

    def _row_to_conflict(self, row: sqlite3.Row) -> Conflict:
        return Conflict(
            id=row["id"],
            merge_request_id=row["merge_request_id"],
            path=row["path"],
            base_value=self._load_json(row["base_value"], None),
            ours_value=self._load_json(row["ours_value"], None),
            theirs_value=self._load_json(row["theirs_value"], None),
            resolution=ConflictResolution(row["resolution"]),
            resolved_value=self._load_json(row["resolved_value"], None),
            resolved_by=row["resolved_by"] or "",
            resolved_at=self._parse_dt(row["resolved_at"]),
        )

    # ---------- Branch CRUD ----------

    def save_branch(self, branch: Branch) -> Branch:
        """保存 (upsert) 分支"""
        conn = sqlite3.connect(self.db_path)
        try:
            conn.execute(
                """
                INSERT OR REPLACE INTO branches (
                    id, name, ontology_id, base_version_id, head_version_id,
                    status, description, created_by, created_at, updated_at,
                    merged_at, merge_target_branch_id
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    branch.id,
                    branch.name,
                    branch.ontology_id,
                    branch.base_version_id,
                    branch.head_version_id,
                    branch.status.value,
                    branch.description or "",
                    branch.created_by or "system",
                    self._iso(branch.created_at),
                    self._iso(branch.updated_at),
                    self._iso(branch.merged_at),
                    branch.merge_target_branch_id,
                ),
            )
            conn.commit()
        finally:
            conn.close()
        return branch

    def get_branch(self, branch_id: str) -> Optional[Branch]:
        conn = sqlite3.connect(self.db_path)
        try:
            conn.row_factory = sqlite3.Row
            row = conn.execute(
                "SELECT * FROM branches WHERE id = ?", (branch_id,)
            ).fetchone()
        finally:
            conn.close()
        return self._row_to_branch(row) if row else None

    def list_branches(self) -> List[Branch]:
        conn = sqlite3.connect(self.db_path)
        try:
            conn.row_factory = sqlite3.Row
            rows = conn.execute(
                "SELECT * FROM branches ORDER BY created_at DESC"
            ).fetchall()
        finally:
            conn.close()
        return [self._row_to_branch(r) for r in rows]

    def list_branches_by_ontology(self, ontology_id: str) -> List[Branch]:
        conn = sqlite3.connect(self.db_path)
        try:
            conn.row_factory = sqlite3.Row
            rows = conn.execute(
                "SELECT * FROM branches WHERE ontology_id = ? "
                "ORDER BY created_at DESC",
                (ontology_id,),
            ).fetchall()
        finally:
            conn.close()
        return [self._row_to_branch(r) for r in rows]

    def get_active_branch(self, ontology_id: str) -> Optional[Branch]:
        conn = sqlite3.connect(self.db_path)
        try:
            conn.row_factory = sqlite3.Row
            row = conn.execute(
                "SELECT * FROM branches WHERE ontology_id = ? AND status = ? "
                "ORDER BY created_at DESC LIMIT 1",
                (ontology_id, BranchStatus.ACTIVE.value),
            ).fetchone()
        finally:
            conn.close()
        return self._row_to_branch(row) if row else None

    def delete_branch(self, branch_id: str) -> bool:
        """删除分支 + 级联删其 MR + MR 的冲突"""
        conn = sqlite3.connect(self.db_path)
        try:
            cur = conn.execute("DELETE FROM branches WHERE id = ?", (branch_id,))
            branch_deleted = cur.rowcount > 0
            # 级联：删除以本分支为 source/target 的 MR 及其冲突
            mr_rows = conn.execute(
                "SELECT id FROM merge_requests WHERE source_branch_id = ? "
                "OR target_branch_id = ?",
                (branch_id, branch_id),
            ).fetchall()
            for (mr_id,) in mr_rows:
                conn.execute(
                    "DELETE FROM conflicts WHERE merge_request_id = ?", (mr_id,)
                )
            conn.execute(
                "DELETE FROM merge_requests WHERE source_branch_id = ? "
                "OR target_branch_id = ?",
                (branch_id, branch_id),
            )
            conn.commit()
        finally:
            conn.close()
        return branch_deleted

    # ---------- MergeRequest ----------

    def save_merge_request(self, mr: MergeRequest) -> MergeRequest:
        conn = sqlite3.connect(self.db_path)
        try:
            conn.execute(
                """
                INSERT OR REPLACE INTO merge_requests (
                    id, source_branch_id, target_branch_id, title, description,
                    conflicts, status, base_snapshot, ours_snapshot,
                    theirs_snapshot, created_by, created_at, updated_at, merged_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    mr.id,
                    mr.source_branch_id,
                    mr.target_branch_id,
                    mr.title,
                    mr.description or "",
                    json.dumps(mr.conflicts or [], ensure_ascii=False, default=str),
                    mr.status.value,
                    json.dumps(mr.base_snapshot or {}, ensure_ascii=False, default=str),
                    json.dumps(mr.ours_snapshot or {}, ensure_ascii=False, default=str),
                    json.dumps(mr.theirs_snapshot or {}, ensure_ascii=False, default=str),
                    mr.created_by or "system",
                    self._iso(mr.created_at),
                    self._iso(mr.updated_at),
                    self._iso(mr.merged_at),
                ),
            )
            conn.commit()
        finally:
            conn.close()
        return mr

    def get_merge_request(self, mr_id: str) -> Optional[MergeRequest]:
        conn = sqlite3.connect(self.db_path)
        try:
            conn.row_factory = sqlite3.Row
            row = conn.execute(
                "SELECT * FROM merge_requests WHERE id = ?", (mr_id,)
            ).fetchone()
        finally:
            conn.close()
        return self._row_to_mr(row) if row else None

    def list_merge_requests(
        self,
        branch_id: Optional[str] = None,
        status: Optional[str] = None,
    ) -> List[MergeRequest]:
        sql = "SELECT * FROM merge_requests WHERE 1=1"
        params: List[Any] = []
        if branch_id:
            sql += " AND (source_branch_id = ? OR target_branch_id = ?)"
            params.extend([branch_id, branch_id])
        if status:
            sql += " AND status = ?"
            params.append(status)
        sql += " ORDER BY created_at DESC"
        conn = sqlite3.connect(self.db_path)
        try:
            conn.row_factory = sqlite3.Row
            rows = conn.execute(sql, params).fetchall()
        finally:
            conn.close()
        return [self._row_to_mr(r) for r in rows]

    # ---------- Conflict ----------

    def save_conflicts(self, mr_id: str, conflicts: List[Conflict]) -> None:
        """保存冲突（同 MR 的旧冲突先删）"""
        conn = sqlite3.connect(self.db_path)
        try:
            conn.execute(
                "DELETE FROM conflicts WHERE merge_request_id = ?", (mr_id,)
            )
            for c in conflicts:
                conn.execute(
                    """
                    INSERT INTO conflicts (
                        id, merge_request_id, path, base_value, ours_value,
                        theirs_value, resolution, resolved_value,
                        resolved_by, resolved_at
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        c.id,
                        c.merge_request_id,
                        c.path,
                        json.dumps(c.base_value, ensure_ascii=False, default=str),
                        json.dumps(c.ours_value, ensure_ascii=False, default=str),
                        json.dumps(c.theirs_value, ensure_ascii=False, default=str),
                        c.resolution.value,
                        json.dumps(c.resolved_value, ensure_ascii=False, default=str),
                        c.resolved_by or "",
                        self._iso(c.resolved_at),
                    ),
                )
            conn.commit()
        finally:
            conn.close()

    def list_conflicts(self, mr_id: str) -> List[Conflict]:
        conn = sqlite3.connect(self.db_path)
        try:
            conn.row_factory = sqlite3.Row
            rows = conn.execute(
                "SELECT * FROM conflicts WHERE merge_request_id = ?",
                (mr_id,),
            ).fetchall()
        finally:
            conn.close()
        return [self._row_to_conflict(r) for r in rows]

    def update_conflict_resolution(
        self,
        conflict_id: str,
        resolution: ConflictResolution,
        resolved_value: Any,
        resolved_by: str,
    ) -> Conflict:
        conn = sqlite3.connect(self.db_path)
        try:
            now_iso = self._iso(datetime.now())
            conn.execute(
                """
                UPDATE conflicts
                SET resolution = ?, resolved_value = ?,
                    resolved_by = ?, resolved_at = ?
                WHERE id = ?
                """,
                (
                    resolution.value,
                    json.dumps(resolved_value, ensure_ascii=False, default=str),
                    resolved_by or "",
                    now_iso,
                    conflict_id,
                ),
            )
            conn.commit()
            conn.row_factory = sqlite3.Row
            row = conn.execute(
                "SELECT * FROM conflicts WHERE id = ?", (conflict_id,)
            ).fetchone()
        finally:
            conn.close()
        if row is None:
            raise ValueError(f"Conflict {conflict_id} not found")
        return self._row_to_conflict(row)
