"""TDD：工单事件审计（子项目 D E-11）——只 INSERT、按时间排序。"""
from __future__ import annotations

from odap.biz.semantic_admin.routing_tickets.storage import SQLiteTicketStorage


def _store(tmp_path):
    return SQLiteTicketStorage(db_path=str(tmp_path / "tickets.db"))


def test_append_event_and_list(tmp_path):
    s = _store(tmp_path)
    t = s.create_ticket({"engine": "nl", "expression": "X",
                         "title": "t", "created_by": "alice"})
    s.append_event(t["id"], event_type="created", actor="alice")
    s.append_event(t["id"], event_type="commented", actor="bob", note="hi")
    ev = s.list_events(t["id"])
    assert [e["event_type"] for e in ev] == ["created", "commented"]
    assert ev[1]["note"] == "hi"


def test_events_are_append_only(tmp_path):
    s = _store(tmp_path)
    t = s.create_ticket({"engine": "nl", "expression": "X",
                         "title": "t", "created_by": "a"})
    for i in range(3):
        s.append_event(t["id"], event_type="commented", actor="a", note=str(i))
    assert len(s.list_events(t["id"])) == 3


def test_event_payload_roundtrip(tmp_path):
    s = _store(tmp_path)
    t = s.create_ticket({"engine": "nl", "expression": "X",
                         "title": "t", "created_by": "a"})
    s.append_event(t["id"], event_type="priority_changed", actor="a",
                   payload={"from": "P2", "to": "P0"})
    ev = s.list_events(t["id"])[0]
    assert ev["payload"] == {"from": "P2", "to": "P0"}


def test_sla_breached_computed_on_read(tmp_path):
    s = _store(tmp_path)
    t = s.create_ticket({"engine": "nl", "expression": "X", "title": "t",
                         "created_by": "a", "sla_deadline": "2020-01-01T00:00:00+00:00"})
    got = s.get_ticket(t["id"])
    assert got["sla_breached"] is True
