"""TDD：promote tool 路径（子项目 D E-5/E-13）。

tool 层缺口 promote → 建工单（open/P2/sla_deadline=now+72h），写 created 事件，
gap 状态 promoted + promoted_ticket_id 回填；route-preview 无副作用。
"""
import pytest

from odap.biz.semantic_admin.gap_pool.models import (
    GapLayer,
    GapSignalSource,
    GapStatus,
)
from odap.biz.semantic_admin.gap_pool.services import GapService
from odap.biz.semantic_admin.gap_pool.storage import SQLiteGapStorage
from odap.biz.semantic_admin.routing_tickets.services.ticket_service import (
    TicketService,
)
from odap.biz.semantic_admin.routing_tickets.storage import SQLiteTicketStorage


@pytest.fixture
def gap_store(tmp_path):
    return SQLiteGapStorage(db_path=str(tmp_path / "concept_gaps.db"))


@pytest.fixture
def ticket_store(tmp_path):
    return SQLiteTicketStorage(db_path=str(tmp_path / "tickets.db"))


def _tool_gap(gap_store, expr="找相似武将", engine="nl_engine"):
    return gap_store.record_signal(
        GapSignalSource.NL_QUERY_UNANSWERED, expr,
        workspace_id="ws1", domain_id="d1",
        attribution={"layer": GapLayer.TOOL.value, "target_ref": engine},
    )


def _svc(gap_store, ticket_store):
    svc = GapService(storage=gap_store)
    svc._ticket_service_factory = lambda: TicketService(storage=ticket_store)
    return svc


def test_tool_promote_creates_ticket(gap_store, ticket_store):
    gap = _tool_gap(gap_store)
    svc = _svc(gap_store, ticket_store)

    r = svc.promote(gap["id"], actor="alice")

    assert r["status"] == "ok"
    assert r["layer"] == "tool"
    assert r["routed_to"] == "tool_routing"
    tid = r["ticket_id"]
    assert tid

    t = ticket_store.get_ticket(tid)
    assert t["status"] == "open"
    assert t["priority"] == "P2"
    assert t["engine"] == "nl_engine"
    assert t["gap_id"] == gap["id"]
    assert t["sla_deadline"]

    # created 事件（D-D13 审计）
    events = ticket_store.list_events(tid)
    assert [e["event_type"] for e in events] == ["created"]

    # gap 回填
    g2 = gap_store.get_gap(gap["id"])
    assert g2["status"] == GapStatus.PROMOTED.value
    assert g2["promoted_ticket_id"] == tid


def test_tool_promote_missing_engine_falls_back(gap_store, ticket_store):
    """归因无 target_ref → engine=unknown_engine（不造数、不崩）。"""
    gap = gap_store.record_signal(
        GapSignalSource.NL_QUERY_UNANSWERED, "无语义引擎",
        workspace_id="ws1", domain_id="d1",
        attribution={"layer": GapLayer.TOOL.value},
    )
    svc = _svc(gap_store, ticket_store)

    r = svc.promote(gap["id"], actor="alice")

    assert r["status"] == "ok"
    assert ticket_store.get_ticket(r["ticket_id"])["engine"] == "unknown_engine"


def test_tool_promote_is_idempotent(gap_store, ticket_store):
    gap = _tool_gap(gap_store)
    svc = _svc(gap_store, ticket_store)

    first = svc.promote(gap["id"], actor="alice")
    second = svc.promote(gap["id"], actor="alice")

    assert second.get("already_promoted") is True
    assert second["ticket_id"] == first["ticket_id"]
    _, total = ticket_store.list_tickets()
    assert total == 1


def test_route_preview_has_no_side_effect(gap_store):
    gap = _tool_gap(gap_store)
    svc = GapService(storage=gap_store)

    r = svc.route_preview(gap["id"])

    assert r["status"] == "ok"
    assert r["layer"] == "tool"
    assert r["routed_to"] == "tool_routing"
    assert r["target_kind"] == "engine"
    assert r["engine"] == "nl_engine"
    # 无副作用：gap 状态不变
    assert gap_store.get_gap(gap["id"])["status"] == GapStatus.OPEN.value


def test_route_preview_missing_gap(gap_store):
    svc = GapService(storage=gap_store)
    r = svc.route_preview("nope")
    assert r["status"] == "error"
    assert r["code"] == "GAP_NOT_FOUND_404"
