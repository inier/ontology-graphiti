"""TDD：工单服务（子项目 D E-9/E-11）——状态机 + 指派 + 事件审计。"""
from __future__ import annotations

from odap.biz.semantic_admin.routing_tickets.services.ticket_service import TicketService
from odap.biz.semantic_admin.routing_tickets.storage import SQLiteTicketStorage


def _svc(tmp_path):
    return TicketService(storage=SQLiteTicketStorage(
        db_path=str(tmp_path / "tickets.db")))


_GAP = {"id": "g1", "expression": "司马懿", "scope_key": "ws::sanguo"}


def test_create_from_gap_open_p2_with_sla(tmp_path):
    svc = _svc(tmp_path)
    r = svc.create_from_gap(_GAP, actor="alice", engine="nl_engine")
    assert r["status"] == "ok"
    t = r["ticket"]
    assert t["status"] == "open"
    assert t["priority"] == "P2"
    assert t["sla_deadline"] is not None
    assert t["engine"] == "nl_engine"
    # created 事件
    ev = svc.events(t["id"])["events"]
    assert ev[0]["event_type"] == "created"


def test_assign_transitions_open_to_assigned(tmp_path):
    svc = _svc(tmp_path)
    tid = svc.create_from_gap(_GAP, actor="alice")["ticket"]["id"]
    r = svc.assign(tid, actor="alice", assignee="bob")
    assert r["ticket"]["status"] == "assigned"
    assert r["ticket"]["assignee"] == "bob"


def test_assign_with_priority_recomputes_sla_and_logs(tmp_path):
    svc = _svc(tmp_path)
    tid = svc.create_from_gap(_GAP, actor="alice")["ticket"]["id"]
    svc.assign(tid, actor="alice", assignee="bob", priority="P0")
    types = [e["event_type"] for e in svc.events(tid)["events"]]
    assert "assigned" in types and "priority_changed" in types


def test_transition_happy_path(tmp_path):
    svc = _svc(tmp_path)
    tid = svc.create_from_gap(_GAP, actor="alice")["ticket"]["id"]
    svc.assign(tid, actor="alice", assignee="bob")
    assert svc.transition(tid, to_status="in_progress", actor="bob")["status"] == "ok"
    r = svc.transition(tid, to_status="resolved", actor="bob", note="修复路由")
    assert r["ticket"]["status"] == "resolved"
    assert r["ticket"]["resolution_note"] == "修复路由"
    assert svc.transition(tid, to_status="closed", actor="bob")["status"] == "ok"


def test_invalid_transition_rejected(tmp_path):
    svc = _svc(tmp_path)
    tid = svc.create_from_gap(_GAP, actor="alice")["ticket"]["id"]
    r = svc.transition(tid, to_status="resolved", actor="alice")   # open→resolved 非法
    assert r["status"] == "error"
    assert r["code"] == "INVALID_TICKET_TRANSITION"


def test_comment_appends_event(tmp_path):
    svc = _svc(tmp_path)
    tid = svc.create_from_gap(_GAP, actor="alice")["ticket"]["id"]
    assert svc.comment(tid, note="已联系引擎 owner", actor="bob")["status"] == "ok"
    types = [e["event_type"] for e in svc.events(tid)["events"]]
    assert "commented" in types


def test_stats_aggregates(tmp_path):
    svc = _svc(tmp_path)
    svc.create_from_gap(_GAP, actor="a", engine="nl_engine")
    tid2 = svc.create_from_gap({**_GAP, "id": "g2"}, actor="a", engine="mdl_engine")["ticket"]["id"]
    svc.assign(tid2, actor="a", assignee="b", priority="P0")
    s = svc.stats()
    assert s["total"] == 2
    assert s["by_status"].get("open") == 1
    assert s["by_status"].get("assigned") == 1
    assert s["by_priority"].get("P0") == 1


def test_assign_terminal_rejected(tmp_path):
    svc = _svc(tmp_path)
    tid = svc.create_from_gap(_GAP, actor="a")["ticket"]["id"]
    svc.transition(tid, to_status="rejected", actor="a")
    r = svc.assign(tid, actor="a", assignee="b")
    assert r["status"] == "error"
    assert r["code"] == "TICKET_TERMINAL"
