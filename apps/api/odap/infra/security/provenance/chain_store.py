"""溯源链存储（P0-3）：追加式封存 + 可复算校验。

设计取舍：

* **写时封存，读时复算** —— 只把「内容指纹 + 前序链哈希 + 链哈希」写进独立
  SQLite 表；校验时重新从审计事件算内容指纹，再与封存值比对。若只在导出时
  现算整条链，审计表被改写后依然能算出「自洽」的链，篡改不可见。
* **追加式，不覆盖** —— ``event_id`` 唯一，重复封存显式跳过并计数，绝不
  upsert（覆盖会抹掉原始封存证据）。
* **未封存必须显式** —— 校验结果区分 ``unsealed`` / ``tampered`` /
  ``broken_chain``，不使用「没发现问题 = 通过」的含糊语义。

存储位置遵循 AGENTS.md 规则 13：默认落在 ``apps/api/data/provenance_chain.db``，
可用 ``DATA_DIR`` 覆盖。
"""

from __future__ import annotations

import logging
import os
import sqlite3
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any, Dict, Iterable, List, Mapping, Optional

from .integrity import (
    GENESIS_DIGEST,
    chain_digest,
    event_digest,
    event_key,
)

logger = logging.getLogger(__name__)

_DEFAULT_DB_DIR = os.path.join(
    os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(
        os.path.dirname(os.path.abspath(__file__)))))),
    "data",
)

_TABLE_DDL = """
CREATE TABLE IF NOT EXISTS provenance_chain (
    seq           INTEGER PRIMARY KEY AUTOINCREMENT,
    event_id      TEXT NOT NULL UNIQUE,
    workspace_id  TEXT,
    event_digest  TEXT NOT NULL,
    prev_digest   TEXT NOT NULL,
    chain_hash    TEXT NOT NULL,
    sealed_at     TEXT NOT NULL
)
"""

_INDEX_DDL = """
CREATE INDEX IF NOT EXISTS idx_provenance_chain_workspace
    ON provenance_chain (workspace_id, seq)
"""


def _utc_now_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def _default_db_path() -> str:
    data_dir = os.environ.get("DATA_DIR") or _DEFAULT_DB_DIR
    return os.path.join(data_dir, "provenance_chain.db")


@dataclass(frozen=True)
class ChainLink:
    """一条已封存的链节。"""

    seq: int
    event_id: str
    workspace_id: Optional[str]
    event_digest: str
    prev_digest: str
    chain_hash: str
    sealed_at: str

    def to_dict(self) -> Dict[str, Any]:
        return {
            "seq": self.seq,
            "event_id": self.event_id,
            "workspace_id": self.workspace_id,
            "event_digest": self.event_digest,
            "prev_digest": self.prev_digest,
            "chain_hash": self.chain_hash,
            "sealed_at": self.sealed_at,
        }


def _row_to_link(row: sqlite3.Row) -> ChainLink:
    return ChainLink(
        seq=row["seq"],
        event_id=row["event_id"],
        workspace_id=row["workspace_id"],
        event_digest=row["event_digest"],
        prev_digest=row["prev_digest"],
        chain_hash=row["chain_hash"],
        sealed_at=row["sealed_at"],
    )


def _sort_key(event: Mapping[str, Any]):
    """封存顺序：时间升序，同一时间按主键升序，保证跨批次可复现。"""
    return (str(event.get("timestamp") or ""), event_key(event))


class ProvenanceChainStore:
    """溯源链的追加式存储与校验器。"""

    def __init__(self, db_path: Optional[str] = None):
        self.db_path = db_path or _default_db_path()
        parent = os.path.dirname(os.path.abspath(self.db_path))
        if parent:
            os.makedirs(parent, exist_ok=True)
        self._init_db()

    # -- 基础设施 ---------------------------------------------------------

    def _connect(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        return conn

    def _init_db(self) -> None:
        conn = self._connect()
        try:
            conn.execute(_TABLE_DDL)
            conn.execute(_INDEX_DDL)
            conn.commit()
        finally:
            conn.close()

    # -- 读取 -------------------------------------------------------------

    def head(self) -> Optional[ChainLink]:
        conn = self._connect()
        try:
            row = conn.execute(
                "SELECT * FROM provenance_chain ORDER BY seq DESC LIMIT 1"
            ).fetchone()
        finally:
            conn.close()
        return _row_to_link(row) if row else None

    def get(self, event_id: str) -> Optional[ChainLink]:
        conn = self._connect()
        try:
            row = conn.execute(
                "SELECT * FROM provenance_chain WHERE event_id = ?", (event_id,)
            ).fetchone()
        finally:
            conn.close()
        return _row_to_link(row) if row else None

    def links(self) -> List[ChainLink]:
        conn = self._connect()
        try:
            rows = conn.execute(
                "SELECT * FROM provenance_chain ORDER BY seq ASC"
            ).fetchall()
        finally:
            conn.close()
        return [_row_to_link(row) for row in rows]

    def count(self) -> int:
        conn = self._connect()
        try:
            row = conn.execute("SELECT COUNT(*) AS n FROM provenance_chain").fetchone()
        finally:
            conn.close()
        return int(row["n"]) if row else 0

    # -- 封存 -------------------------------------------------------------

    def seal(self, events: Iterable[Mapping[str, Any]]) -> Dict[str, Any]:
        """把事件追加进链。已封存的显式跳过，不覆盖。

        Returns:
            {"status": "ok", "sealed": n, "skipped": m,
             "head": {...}|None, "skipped_event_ids": [...]}
        """
        ordered = sorted(list(events), key=_sort_key)
        sealed = 0
        skipped_ids: List[str] = []

        conn = self._connect()
        try:
            with conn:  # 单事务：保证 head 读取与追加之间不留竞态窗口
                row = conn.execute(
                    "SELECT chain_hash FROM provenance_chain ORDER BY seq DESC LIMIT 1"
                ).fetchone()
                prev_digest = row["chain_hash"] if row else GENESIS_DIGEST

                for event in ordered:
                    key = event_key(event)
                    exists = conn.execute(
                        "SELECT 1 FROM provenance_chain WHERE event_id = ?", (key,)
                    ).fetchone()
                    if exists:
                        skipped_ids.append(key)
                        continue

                    digest = event_digest(event)
                    link_hash = chain_digest(prev_digest, digest)
                    conn.execute(
                        "INSERT INTO provenance_chain "
                        "(event_id, workspace_id, event_digest, prev_digest, chain_hash, sealed_at) "
                        "VALUES (?, ?, ?, ?, ?, ?)",
                        (
                            key,
                            event.get("workspace_id"),
                            digest,
                            prev_digest,
                            link_hash,
                            _utc_now_iso(),
                        ),
                    )
                    prev_digest = link_hash
                    sealed += 1
        finally:
            conn.close()

        head = self.head()
        return {
            "status": "ok",
            "sealed": sealed,
            "skipped": len(skipped_ids),
            "skipped_event_ids": skipped_ids,
            "head": head.to_dict() if head else None,
        }

    # -- 校验 -------------------------------------------------------------

    def verify(self, events: Iterable[Mapping[str, Any]]) -> Dict[str, Any]:
        """校验窗口内事件与已封存链的一致性。

        ``valid`` 只在「窗口内全部已封存 + 内容指纹一致 + 链路自洽」时为 True；
        未封存不算通过，避免「没发现问题 = 没问题」的伪绿。
        """
        ordered = sorted(list(events), key=_sort_key)
        all_links = self.links()
        by_id = {link.event_id: link for link in all_links}

        broken_links: List[Dict[str, Any]] = []
        expected_prev = GENESIS_DIGEST
        for link in all_links:
            if link.prev_digest != expected_prev:
                broken_links.append({
                    "event_id": link.event_id,
                    "reason": "prev_mismatch",
                    "expected_prev": expected_prev,
                    "stored_prev": link.prev_digest,
                })
            recomputed = chain_digest(link.prev_digest, link.event_digest)
            if recomputed != link.chain_hash:
                broken_links.append({
                    "event_id": link.event_id,
                    "reason": "chain_hash_mismatch",
                    "expected_chain_hash": recomputed,
                    "stored_chain_hash": link.chain_hash,
                })
            expected_prev = link.chain_hash

        unsealed: List[str] = []
        tampered: List[Dict[str, Any]] = []
        for event in ordered:
            key = event_key(event)
            link = by_id.get(key)
            if link is None:
                unsealed.append(key)
                continue
            actual = event_digest(event)
            if actual != link.event_digest:
                tampered.append({
                    "event_id": key,
                    "sealed_digest": link.event_digest,
                    "actual_digest": actual,
                })

        if tampered or broken_links:
            reason = "tampered" if tampered else "broken_chain"
        elif unsealed:
            reason = "unsealed"
        elif not ordered:
            # 空窗口不能算「校验通过」——什么都没验，就没有资格报告有效
            reason = "empty_window"
        else:
            reason = None

        valid = reason is None
        if not valid:
            logger.warning(
                "Provenance chain verify failed: reason=%s tampered=%d broken=%d unsealed=%d",
                reason, len(tampered), len(broken_links), len(unsealed),
            )

        head = all_links[-1].to_dict() if all_links else None
        return {
            "status": "ok" if valid else "error",
            "valid": valid,
            "reason": reason,
            "checked": len(ordered),
            "sealed_total": len(all_links),
            "unsealed_event_ids": unsealed,
            "tampered": tampered,
            "broken_links": broken_links,
            "head": head,
        }


__all__ = ["ChainLink", "ProvenanceChainStore"]
