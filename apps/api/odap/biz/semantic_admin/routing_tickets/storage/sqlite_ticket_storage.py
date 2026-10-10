"""路由工单 SQLite 存储（ADR-090 D-D6/D-D13）——两表：工单 + 事件审计（只 INSERT）。"""
from __future__ import annotations

import json
import os
import sqlite3
import uuid
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Tuple

from ..models.ticket import is_breached


def _utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


class SQLiteTicketStorage:
    def __init__(self, db_path: Optional[str] = None):
        self.db_path = db_path or os.path.join(
            os.environ.get("DATA_DIR", os.path.join(os.getcwd(), "data")),
            "routing_tickets.db",
        )
        os.makedirs(os.path.dirname(self.db_path), exist_ok=True)
        self._init_db()

    def _init_db(self) -> None:
        conn = sqlite3.connect(self.db_path)
        try:
            conn.executescript(
                """
                CREATE TABLE IF NOT EXISTS tool_routing_tickets (
                    id TEXT PRIMARY KEY,
                    gap_id TEXT,
                    engine TEXT NOT NULL,
                    expression TEXT NOT NULL,
                    scope_key TEXT NOT NULL,
                    title TEXT NOT NULL,
                    description TEXT,
                    priority TEXT NOT NULL DEFAULT 'P2',
                    status TEXT NOT NULL DEFAULT 'open',
                    assignee TEXT,
                    sla_deadline TEXT,
                    created_by TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL,
                    resolved_at TEXT,
                    resolved_by TEXT,
                    resolution_note TEXT
                );
                CREATE INDEX IF NOT EXISTS idx_ticket_status   ON tool_routing_tickets(status);
                CREATE INDEX IF NOT EXISTS idx_ticket_assignee ON tool_routing_tickets(assignee);
                CREATE INDEX IF NOT EXISTS idx_ticket_priority ON tool_routing_tickets(priority);
                CREATE INDEX IF NOT EXISTS idx_ticket_gap      ON tool_routing_tickets(gap_id);

                CREATE TABLE IF NOT EXISTS tool_routing_ticket_events (
                    id TEXT PRIMARY KEY,
                    ticket_id TEXT NOT NULL,
                    event_type TEXT NOT NULL,
                    from_status TEXT,
                    to_status TEXT,
                    actor TEXT NOT NULL,
                    note TEXT,
                    payload_json TEXT,
                    created_at TEXT NOT NULL
                );
                CREATE INDEX IF NOT EXISTS idx_ticket_event_ticket
                    ON tool_routing_ticket_events(ticket_id);
                """
            )
            conn.commit()
        finally:
            conn.close()

    # ── 工单 ───────────────────────────────────────────────────────────

    def create_ticket(self, ticket: Dict[str, Any]) -> Dict[str, Any]:
        now = _utc_now_iso()
        rec = {
            "id": ticket.get("id") or str(uuid.uuid4()),
            "gap_id": ticket.get("gap_id"),
            "engine": ticket["engine"],
            "expression": ticket["expression"],
            "scope_key": ticket.get("scope_key") or "-",
            "title": ticket["title"],
            "description": ticket.get("description"),
            "priority": ticket.get("priority") or "P2",
            "status": ticket.get("status") or "open",
            "assignee": ticket.get("assignee"),
            "sla_deadline": ticket.get("sla_deadline"),
            "created_by": ticket.get("created_by") or "system",
            "created_at": ticket.get("created_at") or now,
            "updated_at": now,
            "resolved_at": ticket.get("resolved_at"),
            "resolved_by": ticket.get("resolved_by"),
            "resolution_note": ticket.get("resolution_note"),
        }
        conn = sqlite3.connect(self.db_path)
        try:
            conn.execute(
                """INSERT INTO tool_routing_tickets (
                    id, gap_id, engine, expression, scope_key, title, description,
                    priority, status, assignee, sla_deadline, created_by,
                    created_at, updated_at, resolved_at, resolved_by, resolution_note
                ) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
                (rec["id"], rec["gap_id"], rec["engine"], rec["expression"],
                 rec["scope_key"], rec["title"], rec["description"],
                 rec["priority"], rec["status"], rec["assignee"],
                 rec["sla_deadline"], rec["created_by"], rec["created_at"],
                 rec["updated_at"], rec["resolved_at"], rec["resolved_by"],
                 rec["resolution_note"]),
            )
            conn.commit()
        finally:
            conn.close()
        return rec

    def get_ticket(self, ticket_id: str) -> Optional[Dict[str, Any]]:
        conn = sqlite3.connect(self.db_path)
        try:
            conn.row_factory = sqlite3.Row
            row = conn.execute(
                "SELECT * FROM tool_routing_tickets WHERE id=?", (ticket_id,)
            ).fetchone()
        finally:
            conn.close()
        return self._ticket_dict(row) if row else None

    _UPDATABLE = {
        "status", "assignee", "priority", "sla_deadline",
        "resolved_at", "resolved_by", "resolution_note", "title",
        "description", "engine",
    }

    def update_ticket(self, ticket_id: str, **fields: Any) -> bool:
        sets, params = ["updated_at=?"], [_utc_now_iso()]
        for k, v in fields.items():
            if k in self._UPDATABLE:
                sets.append(f"{k}=?")
                params.append(v)
        params.append(ticket_id)
        conn = sqlite3.connect(self.db_path)
        try:
            cur = conn.execute(
                f"UPDATE tool_routing_tickets SET {', '.join(sets)} WHERE id=?",
                params,
            )
            conn.commit()
            return cur.rowcount > 0
        finally:
            conn.close()

    def list_tickets(
        self, *, status: Optional[str] = None, priority: Optional[str] = None,
        assignee: Optional[str] = None, engine: Optional[str] = None,
        page: int = 1, page_size: int = 20,
    ) -> Tuple[List[Dict[str, Any]], int]:
        where, params = [], []
        if status:
            where.append("status=?")
            params.append(status)
        if priority:
            where.append("priority=?")
            params.append(priority)
        if assignee:
            where.append("assignee=?")
            params.append(assignee)
        if engine:
            where.append("engine=?")
            params.append(engine)
        clause = ("WHERE " + " AND ".join(where)) if where else ""
        conn = sqlite3.connect(self.db_path)
        try:
            conn.row_factory = sqlite3.Row
            total = conn.execute(
                f"SELECT COUNT(*) AS c FROM tool_routing_tickets {clause}", params
            ).fetchone()["c"]
            rows = conn.execute(
                f"""SELECT * FROM tool_routing_tickets {clause}
                    ORDER BY created_at DESC LIMIT ? OFFSET ?""",
                (*params, int(page_size), max(0, (int(page) - 1) * int(page_size))),
            ).fetchall()
        finally:
            conn.close()
        return [self._ticket_dict(r) for r in rows], int(total)

    # ── 事件审计（只 INSERT，D-D13） ────────────────────────────────────

    def append_event(
        self, ticket_id: str, *, event_type: str, actor: str,
        from_status: Optional[str] = None, to_status: Optional[str] = None,
        note: Optional[str] = None, payload: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        rec = {
            "id": str(uuid.uuid4()),
            "ticket_id": ticket_id,
            "event_type": event_type,
            "from_status": from_status,
            "to_status": to_status,
            "actor": actor,
            "note": note,
            "payload_json": json.dumps(payload or {}, ensure_ascii=False),
            "created_at": _utc_now_iso(),
        }
        conn = sqlite3.connect(self.db_path)
        try:
            conn.execute(
                """INSERT INTO tool_routing_ticket_events (
                    id, ticket_id, event_type, from_status, to_status,
                    actor, note, payload_json, created_at
                ) VALUES (?,?,?,?,?,?,?,?,?)""",
                (rec["id"], rec["ticket_id"], rec["event_type"],
                 rec["from_status"], rec["to_status"], rec["actor"],
                 rec["note"], rec["payload_json"], rec["created_at"]),
            )
            conn.commit()
        finally:
            conn.close()
        return rec

    def list_events(self, ticket_id: str) -> List[Dict[str, Any]]:
        conn = sqlite3.connect(self.db_path)
        try:
            conn.row_factory = sqlite3.Row
            rows = conn.execute(
                """SELECT * FROM tool_routing_ticket_events
                   WHERE ticket_id=? ORDER BY created_at ASC""",
                (ticket_id,),
            ).fetchall()
        finally:
            conn.close()
        out = []
        for r in rows:
            d = dict(r)
            try:
                d["payload"] = json.loads(d.pop("payload_json") or "{}")
            except (ValueError, TypeError):
                d["payload"] = {}
            out.append(d)
        return out

    # ── 内部 ───────────────────────────────────────────────────────────

    @staticmethod
    def _ticket_dict(row: sqlite3.Row) -> Dict[str, Any]:
        d = dict(row)
        d["sla_breached"] = is_breached(d.get("status"), d.get("sla_deadline"))
        return d


__all__ = ["SQLiteTicketStorage"]
