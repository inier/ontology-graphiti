"""TDD：工单状态机（子项目 D E-8）。"""
from __future__ import annotations

from odap.biz.semantic_admin.routing_tickets.models.ticket import (
    TICKET_TRANSITIONS, TERMINAL_STATUSES, TicketStatus,
)


def test_transition_table_shape():
    assert TICKET_TRANSITIONS["open"] == ["assigned", "rejected"]
    assert TICKET_TRANSITIONS["resolved"] == ["closed", "in_progress"]
    assert TICKET_TRANSITIONS["rejected"] == []
    assert TICKET_TRANSITIONS["closed"] == []


def test_open_cannot_jump_to_resolved():
    assert "resolved" not in TICKET_TRANSITIONS["open"]


def test_terminal_statuses():
    assert set(TERMINAL_STATUSES) == {"rejected", "closed"}


def test_full_happy_path_reachable():
    path = ["open", "assigned", "in_progress", "resolved", "closed"]
    for a, b in zip(path, path[1:]):
        assert b in TICKET_TRANSITIONS[a]


def test_enum_values():
    assert TicketStatus.IN_PROGRESS.value == "in_progress"
    assert str(TicketStatus.OPEN) == "open"
