"""wiki_versions 数据访问（版本快照，只增不改：AC-03 / AC-05 / AC-07）。

版本快照一旦写入即不可变 —— 本 Repository 故意不提供 update/delete 方法，
使「物理删除版本」在数据访问层就不可达（AC-07 要求归档保留全部版本）。
"""

from __future__ import annotations

import sqlite3
from typing import List, Optional

from odap.biz.knowledge.wiki.models.entry import WikiVersion
from odap.infra.storage.schema_v2 import connect, ensure_v2_schema


def row_to_version(row: sqlite3.Row) -> WikiVersion:
    return WikiVersion(
        id=row["id"],
        entry_id=row["entry_id"],
        version=row["version"],
        content=row["content"] or "",
        content_hash=row["content_hash"] or "",
        author_id=row["author_id"] or "",
        change_note=row["change_note"] or "",
        created_at=row["created_at"],
    )


class WikiVersionRepository:
    """wiki_versions 表访问对象。"""

    def __init__(self, db_path: Optional[str] = None) -> None:
        self.db_path = db_path
        ensure_v2_schema(db_path)

    def _conn(self) -> sqlite3.Connection:
        return connect(self.db_path)

    def append(self, version: WikiVersion) -> None:
        conn = self._conn()
        try:
            conn.execute(
                """
                INSERT INTO wiki_versions (
                    id, entry_id, version, content, content_hash,
                    author_id, change_note, created_at
                ) VALUES (?,?,?,?,?,?,?,?)
                """,
                (
                    version.id, version.entry_id, version.version, version.content,
                    version.content_hash, version.author_id, version.change_note,
                    version.created_at,
                ),
            )
            conn.commit()
        finally:
            conn.close()

    def list_by_entry(self, entry_id: str) -> List[WikiVersion]:
        """AC-05：按 created_at DESC 返回全部快照。"""
        conn = self._conn()
        try:
            rows = conn.execute(
                "SELECT * FROM wiki_versions WHERE entry_id = ? "
                "ORDER BY created_at DESC, rowid DESC",
                (entry_id,),
            ).fetchall()
        finally:
            conn.close()
        return [row_to_version(r) for r in rows]

    def count_by_entry(self, entry_id: str) -> int:
        conn = self._conn()
        try:
            row = conn.execute(
                "SELECT COUNT(*) AS n FROM wiki_versions WHERE entry_id = ?", (entry_id,)
            ).fetchone()
        finally:
            conn.close()
        return int(row["n"])

    def latest(self, entry_id: str) -> Optional[WikiVersion]:
        versions = self.list_by_entry(entry_id)
        return versions[0] if versions else None


__all__ = ["WikiVersionRepository", "row_to_version"]
