"""路由工单领域模型（ADR-090 子项目 D D-D11/D-D12）。

- 6 态状态机：open → assigned → in_progress → resolved → closed，另 rejected 终态。
- 优先级 P0~P3 → SLA 小时数；sla_breached 读取时计算（不落库）。
"""
from __future__ import annotations

import uuid
from datetime import datetime, timedelta, timezone
from enum import Enum
from typing import Any, Dict, List, Optional


class TicketStatus(str, Enum):
    OPEN = "open"
    ASSIGNED = "assigned"
    IN_PROGRESS = "in_progress"
    RESOLVED = "resolved"
    REJECTED = "rejected"
    CLOSED = "closed"

    def __str__(self) -> str:
        return self.value


class TicketPriority(str, Enum):
    P0 = "P0"
    P1 = "P1"
    P2 = "P2"
    P3 = "P3"

    def __str__(self) -> str:
        return self.value


# 合法状态机转换（D-D11）
TICKET_TRANSITIONS: Dict[str, List[str]] = {
    "open": ["assigned", "rejected"],
    "assigned": ["in_progress", "open", "rejected"],
    "in_progress": ["resolved", "rejected", "assigned"],
    "resolved": ["closed", "in_progress"],
    "rejected": [],
    "closed": [],
}

TERMINAL_STATUSES = ("rejected", "closed")

# 优先级 → SLA 小时（D-D12）
PRIORITY_SLA_HOURS: Dict[str, int] = {"P0": 4, "P1": 24, "P2": 72, "P3": 168}

DEFAULT_PRIORITY = "P2"


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


def _utc_iso(dt: datetime) -> str:
    return dt.isoformat()


def compute_sla_deadline(priority: str, *, from_dt: Optional[datetime] = None) -> str:
    """按优先级派生 SLA 截止时间（ISO）。未知优先级 → 用默认 P2。"""
    hours = PRIORITY_SLA_HOURS.get(priority, PRIORITY_SLA_HOURS[DEFAULT_PRIORITY])
    base = from_dt or _utc_now()
    return _utc_iso(base + timedelta(hours=hours))


def is_breached(status: str, sla_deadline: Optional[str], *,
                now: Optional[datetime] = None) -> bool:
    """违约 = 非终态 ∧ 已过 SLA 截止。截止缺失/不可解析 → False（不造数）。"""
    if status in TERMINAL_STATUSES or not sla_deadline:
        return False
    try:
        dl = datetime.fromisoformat(sla_deadline)
    except (ValueError, TypeError):
        return False
    if dl.tzinfo is None:
        dl = dl.replace(tzinfo=timezone.utc)
    return (now or _utc_now()) > dl


def new_ticket_id() -> str:
    return str(uuid.uuid4())


__all__ = [
    "TicketStatus", "TicketPriority", "TICKET_TRANSITIONS",
    "TERMINAL_STATUSES", "PRIORITY_SLA_HOURS", "DEFAULT_PRIORITY",
    "compute_sla_deadline", "is_breached", "new_ticket_id",
]
