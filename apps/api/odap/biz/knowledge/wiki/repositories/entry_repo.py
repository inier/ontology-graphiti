"""wiki_entries 数据访问（Repository：只做 SQL 与行映射，无业务判断）。

纪律（团队规范：Repository 禁止含业务逻辑）：
- 不抛 ApiError、不判状态机、不算版本号 —— 这些在 service。
- 每次操作短连接，用完即 close（AGENTS.md 规则 8）。
- JSON 列（tags / concept_refs / supersedes）统一 `ensure_ascii=False` 序列化。
"""

from __future__ import annotations

import json
import sqlite3
from typing import Any, Dict, Iterable, List, Optional, Sequence, Tuple

from odap.biz.knowledge.models.common import DocStatus
from odap.biz.knowledge.wiki.models.entry import WikiEntry
from odap.infra.storage.schema_v2 import connect, ensure_v2_schema

#: 允许由上层更新的列白名单（防 SQL 注入 / 防误改主键）
_UPDATABLE = (
    "title", "status", "owner_id", "version", "source_ref", "superseded_by",
    "supersedes", "content_hash", "content", "last_verified", "tags",
    "concept_refs", "workspace_id", "updated_at",
)


def _loads(raw: Any, default: Any) -> Any:
    if raw in (None, ""):
        return default
    if isinstance(raw, (list, dict)):
        return raw
    try:
        return json.loads(raw)
    except (TypeError, ValueError):
        return default


def _dumps(value: Any) -> str:
    return json.dumps(value if value is not None else [], ensure_ascii=False)


def row_to_entry(row: sqlite3.Row) -> WikiEntry:
    """sqlite Row → WikiEntry（citations 由 citation repository 另行装配）。"""
    return WikiEntry(
        id=row["id"],
        title=row["title"],
        content=row["content"] or "",
        status=DocStatus(row["status"]),
        owner=row["owner_id"],
        version=row["version"],
        source_ref=row["source_ref"],
        superseded_by=row["superseded_by"],
        supersedes=_loads(row["supersedes"], []),
        content_hash=row["content_hash"] or "",
        last_verified=row["last_verified"],
        tags=_loads(row["tags"], []),
        concept_refs=_loads(row["concept_refs"], []),
        workspace_id=row["workspace_id"] or "",
        created_at=row["created_at"],
        updated_at=row["updated_at"],
    )


class WikiEntryRepository:
    """wiki_entries 表访问对象。"""

    def __init__(self, db_path: Optional[str] = None) -> None:
        self.db_path = db_path
        ensure_v2_schema(db_path)

    def _conn(self) -> sqlite3.Connection:
        return connect(self.db_path)

    # ── 写 ────────────────────────────────────────────────────────────────
    def insert(self, entry: WikiEntry) -> None:
        conn = self._conn()
        try:
            conn.execute(
                """
                INSERT INTO wiki_entries (
                    id, title, status, owner_id, version, source_ref, superseded_by,
                    supersedes, content_hash, content, last_verified, tags,
                    concept_refs, workspace_id, created_at, updated_at
                ) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)
                """,
                (
                    entry.id, entry.title, entry.status.value, entry.owner, entry.version,
                    entry.source_ref, entry.superseded_by, _dumps(entry.supersedes),
                    entry.content_hash, entry.content, entry.last_verified,
                    _dumps(entry.tags), _dumps(entry.concept_refs), entry.workspace_id,
                    entry.created_at, entry.updated_at,
                ),
            )
            conn.commit()
        finally:
            conn.close()

    def update(self, entry_id: str, fields: Dict[str, Any]) -> int:
        """按白名单更新列，返回受影响行数。"""
        unknown = set(fields) - set(_UPDATABLE)
        if unknown:
            raise ValueError(f"不可更新的列：{sorted(unknown)}")
        if not fields:
            return 0
        assignments = ", ".join(f"{col} = ?" for col in fields)
        values = [
            _dumps(v) if col in ("supersedes", "tags", "concept_refs") else v
            for col, v in fields.items()
        ]
        conn = self._conn()
        try:
            cursor = conn.execute(
                f"UPDATE wiki_entries SET {assignments} WHERE id = ?",
                (*values, entry_id),
            )
            conn.commit()
            return cursor.rowcount
        finally:
            conn.close()

    # ── 读 ────────────────────────────────────────────────────────────────
    def get(self, entry_id: str) -> Optional[WikiEntry]:
        conn = self._conn()
        try:
            row = conn.execute("SELECT * FROM wiki_entries WHERE id = ?", (entry_id,)).fetchone()
        finally:
            conn.close()
        return row_to_entry(row) if row else None

    def get_by_source_ref(self, source_ref: str) -> Optional[WikiEntry]:
        conn = self._conn()
        try:
            row = conn.execute(
                "SELECT * FROM wiki_entries WHERE source_ref = ?", (source_ref,)
            ).fetchone()
        finally:
            conn.close()
        return row_to_entry(row) if row else None

    def find_published_by_hash(
        self, content_hash: str, exclude_id: Optional[str] = None
    ) -> List[WikiEntry]:
        """找出 content_hash 相同且已发布的条目（AC-04 发布拦截依据）。"""
        sql = "SELECT * FROM wiki_entries WHERE content_hash = ? AND status = ?"
        params: List[Any] = [content_hash, DocStatus.PUBLISHED.value]
        if exclude_id:
            sql += " AND id <> ?"
            params.append(exclude_id)
        conn = self._conn()
        try:
            rows = conn.execute(sql, params).fetchall()
        finally:
            conn.close()
        return [row_to_entry(r) for r in rows]

    def list_entries(
        self,
        *,
        status: Optional[str] = None,
        owner: Optional[str] = None,
        q: Optional[str] = None,
        page: int = 1,
        limit: int = 20,
    ) -> Tuple[List[WikiEntry], int]:
        where: List[str] = []
        params: List[Any] = []
        if status:
            where.append("status = ?")
            params.append(status)
        if owner:
            where.append("owner_id = ?")
            params.append(owner)
        if q:
            where.append("(title LIKE ? OR content LIKE ?)")
            like = f"%{q}%"
            params.extend([like, like])
        clause = f" WHERE {' AND '.join(where)}" if where else ""

        conn = self._conn()
        try:
            total = conn.execute(
                f"SELECT COUNT(*) AS n FROM wiki_entries{clause}", params
            ).fetchone()["n"]
            rows = conn.execute(
                f"SELECT * FROM wiki_entries{clause} ORDER BY updated_at DESC LIMIT ? OFFSET ?",
                (*params, limit, max(page - 1, 0) * limit),
            ).fetchall()
        finally:
            conn.close()
        return [row_to_entry(r) for r in rows], int(total)

    def list_by_ids(self, ids: Sequence[str]) -> List[WikiEntry]:
        if not ids:
            return []
        placeholders = ",".join("?" for _ in ids)
        conn = self._conn()
        try:
            rows = conn.execute(
                f"SELECT * FROM wiki_entries WHERE id IN ({placeholders})", list(ids)
            ).fetchall()
        finally:
            conn.close()
        return [row_to_entry(r) for r in rows]

    def list_by_hashes(self, hashes: Iterable[str]) -> List[WikiEntry]:
        values = [h for h in hashes if h]
        if not values:
            return []
        placeholders = ",".join("?" for _ in values)
        conn = self._conn()
        try:
            rows = conn.execute(
                f"SELECT * FROM wiki_entries WHERE content_hash IN ({placeholders})",
                values,
            ).fetchall()
        finally:
            conn.close()
        return [row_to_entry(r) for r in rows]

    def list_all(self) -> List[WikiEntry]:
        conn = self._conn()
        try:
            rows = conn.execute("SELECT * FROM wiki_entries").fetchall()
        finally:
            conn.close()
        return [row_to_entry(r) for r in rows]

    def count_by_status(self) -> Dict[str, int]:
        conn = self._conn()
        try:
            rows = conn.execute(
                "SELECT status, COUNT(*) AS n FROM wiki_entries GROUP BY status"
            ).fetchall()
        finally:
            conn.close()
        return {r["status"]: int(r["n"]) for r in rows}


__all__ = ["WikiEntryRepository", "row_to_entry"]
