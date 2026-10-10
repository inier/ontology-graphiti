"""路由工单服务（ADR-090 D-D6/D-D11/D-D12/D-D13）——状态机 + 指派 + SLA + 事件。

服务层返回 Dict[str, Any]（AGENTS.md 规则 2）；失败用显式 code（规则 14）。
"""
from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Any, Dict, Optional

from ..models.ticket import (
    DEFAULT_PRIORITY,
    PRIORITY_SLA_HOURS,
    TERMINAL_STATUSES,
    TICKET_TRANSITIONS,
    TicketPriority,
    TicketStatus,
    compute_sla_deadline,
)
from ..storage import SQLiteTicketStorage

logger = logging.getLogger(__name__)

_VALID_PRIORITIES = tuple(p.value for p in TicketPriority)
_VALID_STATUSES = tuple(s.value for s in TicketStatus)


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


class TicketService:
    def __init__(self, storage: Optional[SQLiteTicketStorage] = None):
        self.storage = storage or SQLiteTicketStorage()

    # ── 创建 ───────────────────────────────────────────────────────────
    def create_from_gap(
        self, gap: Dict[str, Any], *, actor: str,
        engine: Optional[str] = None, priority: str = DEFAULT_PRIORITY,
    ) -> Dict[str, Any]:
        if priority not in _VALID_PRIORITIES:
            priority = DEFAULT_PRIORITY
        expression = gap.get("expression") or ""
        rec = self.storage.create_ticket({
            "gap_id": gap.get("id"),
            "engine": engine or "unknown_engine",
            "expression": expression,
            "scope_key": gap.get("scope_key") or "-",
            "title": f"检索引擎能力缺口：{expression}",
            "description": (f"缺口 {gap.get('id')} 路由到 tool 层；"
                            f"engine={engine or 'unknown'}"),
            "priority": priority,
            "status": TicketStatus.OPEN.value,
            "sla_deadline": compute_sla_deadline(priority),
            "created_by": actor,
        })
        self.storage.append_event(
            rec["id"], event_type="created", actor=actor,
            to_status=TicketStatus.OPEN.value,
            note=f"由缺口 {gap.get('id')} 创建",
            payload={"priority": priority, "engine": rec["engine"]},
        )
        return {"status": "ok", "ticket": rec}

    # ── 查询 ───────────────────────────────────────────────────────────
    def get(self, ticket_id: str) -> Dict[str, Any]:
        t = self.storage.get_ticket(ticket_id)
        if not t:
            return {"status": "error", "code": "TICKET_NOT_FOUND_404",
                    "message": f"工单 {ticket_id} 不存在"}
        return {"status": "ok", "ticket": t}

    def list(self, **filters: Any) -> Dict[str, Any]:
        page = int(filters.pop("page", 1) or 1)
        page_size = int(filters.pop("page_size", 20) or 20)
        clean = {k: v for k, v in filters.items() if v}
        items, total = self.storage.list_tickets(
            page=page, page_size=page_size, **clean)
        return {"status": "ok", "items": items, "total": total,
                "page": page, "page_size": page_size}

    def events(self, ticket_id: str) -> Dict[str, Any]:
        if not self.storage.get_ticket(ticket_id):
            return {"status": "error", "code": "TICKET_NOT_FOUND_404",
                    "message": f"工单 {ticket_id} 不存在"}
        return {"status": "ok", "ticket_id": ticket_id,
                "events": self.storage.list_events(ticket_id)}

    # ── 指派 / 改优先级 ────────────────────────────────────────────────
    def assign(
        self, ticket_id: str, *, actor: str, assignee: str,
        priority: Optional[str] = None,
    ) -> Dict[str, Any]:
        t = self.storage.get_ticket(ticket_id)
        if not t:
            return {"status": "error", "code": "TICKET_NOT_FOUND_404",
                    "message": f"工单 {ticket_id} 不存在"}
        if t["status"] in TERMINAL_STATUSES:
            return {"status": "error", "code": "TICKET_TERMINAL",
                    "message": f"工单已终态（{t['status']}），不可指派"}
        if not assignee:
            return {"status": "error", "code": "ASSIGNEE_REQUIRED",
                    "message": "assignee 不能为空"}
        fields: Dict[str, Any] = {"assignee": assignee}
        # open → assigned；已在 assigned/in_progress 时仅换人
        if t["status"] == TicketStatus.OPEN.value:
            fields["status"] = TicketStatus.ASSIGNED.value
        if priority:
            if priority not in _VALID_PRIORITIES:
                return {"status": "error", "code": "INVALID_PRIORITY",
                        "message": f"非法 priority: {priority!r}"}
            fields["priority"] = priority
            fields["sla_deadline"] = compute_sla_deadline(priority)
        self.storage.update_ticket(ticket_id, **fields)
        self.storage.append_event(
            ticket_id, event_type="assigned", actor=actor,
            from_status=t["status"], to_status=fields.get("status", t["status"]),
            note=f"指派给 {assignee}" + (f"，优先级 {priority}" if priority else ""),
            payload={"assignee": assignee, "priority": fields.get("priority")},
        )
        if priority:
            self.storage.append_event(
                ticket_id, event_type="priority_changed", actor=actor,
                note=f"优先级 {t.get('priority')} → {priority}",
                payload={"from": t.get("priority"), "to": priority},
            )
        return {"status": "ok", "ticket": self.storage.get_ticket(ticket_id)}

    # ── 状态流转 ───────────────────────────────────────────────────────
    def transition(
        self, ticket_id: str, *, to_status: str, actor: str,
        note: Optional[str] = None,
    ) -> Dict[str, Any]:
        t = self.storage.get_ticket(ticket_id)
        if not t:
            return {"status": "error", "code": "TICKET_NOT_FOUND_404",
                    "message": f"工单 {ticket_id} 不存在"}
        if to_status not in _VALID_STATUSES:
            return {"status": "error", "code": "INVALID_STATUS",
                    "message": f"非法状态: {to_status!r}"}
        allowed = TICKET_TRANSITIONS.get(t["status"], [])
        if to_status not in allowed:
            return {"status": "error", "code": "INVALID_TICKET_TRANSITION",
                    "message": f"不允许从 {t['status']} 流转到 {to_status}"
                               f"（合法目标：{allowed}）"}
        fields: Dict[str, Any] = {"status": to_status}
        if to_status == TicketStatus.RESOLVED.value:
            fields["resolved_at"] = _now_iso()
            fields["resolved_by"] = actor
            fields["resolution_note"] = note
        self.storage.update_ticket(ticket_id, **fields)
        self.storage.append_event(
            ticket_id, event_type="transitioned", actor=actor,
            from_status=t["status"], to_status=to_status, note=note,
        )
        return {"status": "ok", "ticket": self.storage.get_ticket(ticket_id)}

    # ── 评论 ───────────────────────────────────────────────────────────
    def comment(self, ticket_id: str, *, note: str, actor: str) -> Dict[str, Any]:
        if not self.storage.get_ticket(ticket_id):
            return {"status": "error", "code": "TICKET_NOT_FOUND_404",
                    "message": f"工单 {ticket_id} 不存在"}
        if not note:
            return {"status": "error", "code": "NOTE_REQUIRED",
                    "message": "note 不能为空"}
        self.storage.append_event(
            ticket_id, event_type="commented", actor=actor, note=note)
        return {"status": "ok", "ticket_id": ticket_id}

    # ── 统计 ───────────────────────────────────────────────────────────
    def stats(self) -> Dict[str, Any]:
        items, total = self.storage.list_tickets(page=1, page_size=100000)
        by_status: Dict[str, int] = {}
        by_priority: Dict[str, int] = {}
        breached = 0
        for t in items:
            by_status[t["status"]] = by_status.get(t["status"], 0) + 1
            by_priority[t["priority"]] = by_priority.get(t["priority"], 0) + 1
            if t.get("sla_breached"):
                breached += 1
        return {"status": "ok", "total": total, "by_status": by_status,
                "by_priority": by_priority, "breached_count": breached}


_ticket_service_singleton: Optional[TicketService] = None


def get_ticket_service() -> TicketService:
    global _ticket_service_singleton
    if _ticket_service_singleton is None:
        _ticket_service_singleton = TicketService()
    return _ticket_service_singleton


__all__ = ["TicketService", "get_ticket_service"]
