"""`qa_actions` 持久化（AC-42：动作必须关联同一 `trace_id`）。

状态机（唯一合法迁移，越界即拒）：
    proposed ──approve──▶ approved ──execute──▶ executed
        │                     │
        └──reject──▶ rejected └──execute(low 可直接从 proposed)──▶ executed

只做数据访问，不含业务判断（业务规则在 `service.ActionService`）。
"""

from __future__ import annotations

import json
import sqlite3
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from odap.infra.storage.schema_v2 import connect, ensure_v2_schema

_STATUS_OPEN = ("proposed", "approved")


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


class QaActionRepository:
    """`qa_actions` 的读写。"""

    def __init__(self, db_path: Optional[str] = None) -> None:
        self.db_path = db_path
        ensure_v2_schema(db_path)

    def _conn(self) -> sqlite3.Connection:
        return connect(self.db_path)

    def insert_many(self, trace_id: str, actions: List[Dict[str, Any]]) -> List[str]:
        """批量写入 `status=proposed`，返回写库后的 id 列表（与入参同序）。"""
        if not actions:
            return []
        rows = []
        ids = []
        for item in actions:
            action_id = str(item["id"])
            ids.append(action_id)
            rows.append((
                action_id,
                trace_id,
                str(item["action_type"]),
                str(item["risk_level"]),
                json.dumps(item.get("payload") or {}, ensure_ascii=False),
                str(item.get("status") or "proposed"),
                _now(),
            ))
        conn = self._conn()
        try:
            with conn:
                conn.executemany(
                    """
                    INSERT INTO qa_actions (
                        id, trace_id, action_type, risk_level, payload, status, created_at
                    ) VALUES (?,?,?,?,?,?,?)
                    """,
                    rows,
                )
        finally:
            conn.close()
        return ids

    def get(self, action_id: str) -> Optional[Dict[str, Any]]:
        conn = self._conn()
        try:
            row = conn.execute(
                "SELECT * FROM qa_actions WHERE id = ?", (action_id,)
            ).fetchone()
        finally:
            conn.close()
        return _to_dict(row) if row else None

    def list_by_trace(self, trace_id: str) -> List[Dict[str, Any]]:
        conn = self._conn()
        try:
            rows = conn.execute(
                "SELECT * FROM qa_actions WHERE trace_id = ? ORDER BY created_at ASC, id ASC",
                (trace_id,),
            ).fetchall()
        finally:
            conn.close()
        return [_to_dict(r) for r in rows]

    def mark_approved(self, action_id: str, approved_by: str) -> bool:
        return self._update(
            "UPDATE qa_actions SET status='approved', approved_by=? "
            "WHERE id=? AND status='proposed'",
            (approved_by, action_id),
        )

    def mark_rejected(self, action_id: str, approved_by: str) -> bool:
        return self._update(
            "UPDATE qa_actions SET status='rejected', approved_by=? "
            "WHERE id=? AND status='proposed'",
            (approved_by, action_id),
        )

    def mark_executed(self, action_id: str) -> bool:
        """仅允许从 `proposed`（低风险）/`approved`（高风险）迁到 `executed`。"""
        conn = self._conn()
        try:
            with conn:
                cur = conn.execute(
                    "UPDATE qa_actions SET status='executed', executed_at=? "
                    "WHERE id=? AND status IN (?,?)",
                    (_now(), action_id, _STATUS_OPEN[0], _STATUS_OPEN[1]),
                )
                return cur.rowcount == 1
        finally:
            conn.close()

    def _update(self, sql: str, params: tuple) -> bool:
        conn = self._conn()
        try:
            with conn:
                cur = conn.execute(sql, params)
                return cur.rowcount == 1
        finally:
            conn.close()


def _to_dict(row: sqlite3.Row) -> Dict[str, Any]:
    try:
        payload = json.loads(row["payload"]) if row["payload"] else {}
    except (TypeError, ValueError):
        payload = {}
    return {
        "id": row["id"],
        "trace_id": row["trace_id"],
        "action_type": row["action_type"],
        "risk_level": row["risk_level"],
        "payload": payload,
        "status": row["status"],
        "approved_by": row["approved_by"],
        "executed_at": row["executed_at"],
        "created_at": row["created_at"],
    }


__all__ = ["QaActionRepository"]
