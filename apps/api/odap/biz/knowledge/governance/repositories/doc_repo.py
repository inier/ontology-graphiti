"""governed_documents 数据访问（F2 文档纳管，AC-09~AC-14）。

纳管模型与 wiki 条目同构（ARCHITECTURE-v2 §5.2），通过 `source_ref` 双向映射：
- 仓库导入：`upsert_by_source_ref` 保证同一仓库路径只对应一条纳管记录（幂等）。
- `owner_id` 允许为空 —— 为空是**待治理缺陷**（AC-12 MISSING_OWNER），
  不能在写入时拒绝，否则治理检查永远看不到问题。
"""

from __future__ import annotations

import json
import sqlite3
from typing import Any, Dict, Iterable, List, Optional, Sequence, Tuple

from odap.biz.knowledge.models.common import DocStatus
from odap.biz.knowledge.governance.models.doc import GovernedDoc
from odap.infra.storage.schema_v2 import connect, ensure_v2_schema

_UPDATABLE = (
    "title", "status", "owner_id", "version", "source_ref", "superseded_by",
    "supersedes", "content_hash", "content", "last_verified", "role", "tags",
    "updated_at",
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


def row_to_doc(row: sqlite3.Row) -> GovernedDoc:
    return GovernedDoc(
        id=row["id"],
        title=row["title"],
        status=DocStatus(row["status"]),
        owner=row["owner_id"],
        version=row["version"],
        source_ref=row["source_ref"],
        superseded_by=row["superseded_by"],
        supersedes=_loads(row["supersedes"], []),
        content_hash=row["content_hash"] or "",
        last_verified=row["last_verified"],
        role=row["role"] or "",
        tags=_loads(row["tags"], []),
        created_at=row["created_at"],
        updated_at=row["updated_at"],
    )


class GovernedDocRepository:
    """governed_documents 表访问对象。"""

    def __init__(self, db_path: Optional[str] = None) -> None:
        self.db_path = db_path
        ensure_v2_schema(db_path)

    def _conn(self) -> sqlite3.Connection:
        return connect(self.db_path)

    def upsert(self, doc: GovernedDoc) -> str:
        """按 id 或 source_ref 幂等写入，返回最终 id。"""
        existing = self.get(doc.id) if doc.id else None
        if existing is None and doc.source_ref:
            existing = self.get_by_source_ref(doc.source_ref)
        conn = self._conn()
        try:
            if existing is None:
                conn.execute(
                    """
                    INSERT INTO governed_documents (
                        id, title, status, owner_id, version, source_ref, superseded_by,
                        supersedes, content_hash, content, last_verified, role, tags,
                        created_at, updated_at
                    ) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)
                    """,
                    (
                        doc.id, doc.title, doc.status.value, doc.owner, doc.version,
                        doc.source_ref, doc.superseded_by, _dumps(doc.supersedes),
                        doc.content_hash, doc.content, doc.last_verified, doc.role,
                        _dumps(doc.tags), doc.created_at, doc.updated_at,
                    ),
                )
                final_id = doc.id
            else:
                conn.execute(
                    """
                    UPDATE governed_documents SET
                        title = ?, status = ?, owner_id = ?, version = ?, source_ref = ?,
                        superseded_by = ?, supersedes = ?, content_hash = ?, content = ?,
                        last_verified = ?, role = ?, tags = ?, updated_at = ?
                    WHERE id = ?
                    """,
                    (
                        doc.title, doc.status.value, doc.owner, doc.version, doc.source_ref,
                        doc.superseded_by, _dumps(doc.supersedes), doc.content_hash,
                        doc.content, doc.last_verified, doc.role, _dumps(doc.tags),
                        doc.updated_at, existing.id,
                    ),
                )
                final_id = existing.id
            conn.commit()
        finally:
            conn.close()
        return final_id

    def update(self, doc_id: str, fields: Dict[str, Any]) -> int:
        unknown = set(fields) - set(_UPDATABLE)
        if unknown:
            raise ValueError(f"不可更新的列：{sorted(unknown)}")
        if not fields:
            return 0
        assignments = ", ".join(f"{col} = ?" for col in fields)
        values = [
            _dumps(v) if col in ("supersedes", "tags") else v
            for col, v in fields.items()
        ]
        conn = self._conn()
        try:
            cursor = conn.execute(
                f"UPDATE governed_documents SET {assignments} WHERE id = ?",
                (*values, doc_id),
            )
            conn.commit()
            return cursor.rowcount
        finally:
            conn.close()

    def get(self, doc_id: str) -> Optional[GovernedDoc]:
        conn = self._conn()
        try:
            row = conn.execute(
                "SELECT * FROM governed_documents WHERE id = ?", (doc_id,)
            ).fetchone()
        finally:
            conn.close()
        return row_to_doc(row) if row else None

    def get_by_source_ref(self, source_ref: str) -> Optional[GovernedDoc]:
        conn = self._conn()
        try:
            row = conn.execute(
                "SELECT * FROM governed_documents WHERE source_ref = ?", (source_ref,)
            ).fetchone()
        finally:
            conn.close()
        return row_to_doc(row) if row else None

    def list_docs(
        self,
        *,
        status: Optional[str] = None,
        stale_before: Optional[str] = None,
        no_owner: bool = False,
        page: int = 1,
        limit: int = 20,
    ) -> Tuple[List[GovernedDoc], int]:
        where: List[str] = []
        params: List[Any] = []
        if status:
            where.append("status = ?")
            params.append(status)
        if no_owner:
            where.append("(owner_id IS NULL OR owner_id = '')")
        if stale_before:
            where.append("(last_verified IS NULL OR last_verified < ?)")
            params.append(stale_before)
        clause = f" WHERE {' AND '.join(where)}" if where else ""

        conn = self._conn()
        try:
            total = conn.execute(
                f"SELECT COUNT(*) AS n FROM governed_documents{clause}", params
            ).fetchone()["n"]
            rows = conn.execute(
                f"SELECT * FROM governed_documents{clause} "
                "ORDER BY updated_at DESC LIMIT ? OFFSET ?",
                (*params, limit, max(page - 1, 0) * limit),
            ).fetchall()
        finally:
            conn.close()
        return [row_to_doc(r) for r in rows], int(total)

    def list_all(self) -> List[GovernedDoc]:
        conn = self._conn()
        try:
            rows = conn.execute("SELECT * FROM governed_documents").fetchall()
        finally:
            conn.close()
        return [row_to_doc(r) for r in rows]

    def list_by_hashes(self, hashes: Iterable[str]) -> List[GovernedDoc]:
        values = [h for h in hashes if h]
        if not values:
            return []
        placeholders = ",".join("?" for _ in values)
        conn = self._conn()
        try:
            rows = conn.execute(
                f"SELECT * FROM governed_documents WHERE content_hash IN ({placeholders})",
                values,
            ).fetchall()
        finally:
            conn.close()
        return [row_to_doc(r) for r in rows]

    def exists_many(self, ids: Sequence[str]) -> List[str]:
        """返回给定 id 中真实存在的那些（AC-11 悬空引用判定用）。"""
        values = [i for i in ids if i]
        if not values:
            return []
        placeholders = ",".join("?" for _ in values)
        conn = self._conn()
        try:
            rows = conn.execute(
                f"SELECT id FROM governed_documents WHERE id IN ({placeholders})", values
            ).fetchall()
        finally:
            conn.close()
        return [r["id"] for r in rows]


__all__ = ["GovernedDocRepository", "row_to_doc"]
