"""TDD：工单 SLA（子项目 D E-10）。"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone

from odap.biz.semantic_admin.routing_tickets.models.ticket import (
    PRIORITY_SLA_HOURS, compute_sla_deadline, is_breached,
)


def test_priority_sla_hours():
    assert PRIORITY_SLA_HOURS == {"P0": 4, "P1": 24, "P2": 72, "P3": 168}


def test_compute_sla_deadline_by_priority():
    base = datetime(2026, 10, 9, 0, 0, tzinfo=timezone.utc)
    dl = compute_sla_deadline("P0", from_dt=base)
    assert datetime.fromisoformat(dl) == base + timedelta(hours=4)
    dl2 = compute_sla_deadline("P3", from_dt=base)
    assert datetime.fromisoformat(dl2) == base + timedelta(hours=168)


def test_unknown_priority_defaults_p2():
    base = datetime(2026, 10, 9, tzinfo=timezone.utc)
    dl = compute_sla_deadline("PX", from_dt=base)
    # 未知优先级 → 用默认 P2（72h）
    assert datetime.fromisoformat(dl) == base + timedelta(hours=72)


def test_is_breached_true_when_past_deadline_non_terminal():
    past = (datetime(2026, 10, 1, tzinfo=timezone.utc)).isoformat()
    assert is_breached("open", past, now=datetime(2026, 10, 9, tzinfo=timezone.utc)) is True


def test_is_breached_false_when_terminal():
    past = (datetime(2026, 10, 1, tzinfo=timezone.utc)).isoformat()
    # 终态 = rejected / closed（resolved 可复开，非终态）
    for st in ("rejected", "closed"):
        assert is_breached(st, past, now=datetime(2026, 10, 9, tzinfo=timezone.utc)) is False
    # resolved 仍是非终态 → 过期即违约
    assert is_breached("resolved", past, now=datetime(2026, 10, 9, tzinfo=timezone.utc)) is True


def test_is_breached_false_when_future_or_missing():
    future = (datetime(2027, 1, 1, tzinfo=timezone.utc)).isoformat()
    assert is_breached("open", future, now=datetime(2026, 10, 9, tzinfo=timezone.utc)) is False
    assert is_breached("open", None) is False
    assert is_breached("open", "not-a-date") is False
