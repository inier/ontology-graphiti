"""wiki_citations 数据访问（引用图，AC-06 / AC-11）。

引用是「条目 → 外部对象」的有向边；反向查询即「谁引用了本文档」。
悬空引用检测（AC-11）由 governance.verify_service 消费本 Repository，
不在数据层判断 ref 是否可解析（那是业务规则）。
"""

from __future__ import annotations

import sqlite3
from typing import Dict, List, Optional

from odap.biz.knowledge.models.common import Citation, CitationKind
from odap.infra.storage.schema_v2 import connect, ensure_v2_schema


class WikiCitationRepository:
    """wiki_citations 表访问对象。"""

    def __init__(self, db_path: Optional[str] = None) -> None:
        self.db_path = db_path
        ensure_v2_schema(db_path)

    def _conn(self) -> sqlite3.Connection:
        return connect(self.db_path)

    def replace_for_entry(self, entry_id: str, rows: List[Dict[str, str]]) -> None:
        """整体替换某条目的引用集合（PATCH 语义：以提交内容为准）。"""
        conn = self._conn()
        try:
            conn.execute("DELETE FROM wiki_citations WHERE entry_id = ?", (entry_id,))
            conn.executemany(
                "INSERT INTO wiki_citations (id, entry_id, kind, ref, created_at) "
                "VALUES (?,?,?,?,?)",
                [
                    (r["id"], entry_id, r["kind"], r["ref"], r["created_at"])
                    for r in rows
                ],
            )
            conn.commit()
        finally:
            conn.close()

    def append_many(self, entry_id: str, rows: List[Dict[str, str]]) -> None:
        if not rows:
            return
        conn = self._conn()
        try:
            conn.executemany(
                "INSERT INTO wiki_citations (id, entry_id, kind, ref, created_at) "
                "VALUES (?,?,?,?,?)",
                [
                    (r["id"], entry_id, r["kind"], r["ref"], r["created_at"])
                    for r in rows
                ],
            )
            conn.commit()
        finally:
            conn.close()

    def list_outgoing(self, entry_id: str) -> List[Citation]:
        conn = self._conn()
        try:
            rows = conn.execute(
                "SELECT kind, ref FROM wiki_citations WHERE entry_id = ? ORDER BY created_at",
                (entry_id,),
            ).fetchall()
        finally:
            conn.close()
        return [Citation(kind=CitationKind(r["kind"]), ref=r["ref"]) for r in rows]

    def list_incoming(self, ref: str) -> List[Dict[str, str]]:
        """谁引用了 `ref`（返回引用方 entry_id 与 kind）。"""
        conn = self._conn()
        try:
            rows = conn.execute(
                "SELECT entry_id, kind, ref FROM wiki_citations WHERE ref = ? "
                "ORDER BY created_at",
                (ref,),
            ).fetchall()
        finally:
            conn.close()
        return [{"entry_id": r["entry_id"], "kind": r["kind"], "ref": r["ref"]} for r in rows]

    def list_all(self) -> List[Dict[str, str]]:
        conn = self._conn()
        try:
            rows = conn.execute(
                "SELECT id, entry_id, kind, ref, created_at FROM wiki_citations"
            ).fetchall()
        finally:
            conn.close()
        return [dict(r) for r in rows]


__all__ = ["WikiCitationRepository"]
