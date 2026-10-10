"""TDD：promote 路由层（子项目 D E-13）——route-preview 端点 + force_layer 透传。"""
import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from odap.biz.semantic_admin.gap_pool.api.routes import router
from odap.biz.semantic_admin.gap_pool.models import GapLayer, GapSignalSource
from odap.biz.semantic_admin.gap_pool.services import GapService
from odap.biz.semantic_admin.gap_pool.storage import SQLiteGapStorage
from odap.biz.semantic_admin.routing_tickets.services.ticket_service import (
    TicketService,
)
from odap.biz.semantic_admin.routing_tickets.storage import SQLiteTicketStorage


@pytest.fixture
def wired(tmp_path, monkeypatch):
    gstore = SQLiteGapStorage(db_path=str(tmp_path / "concept_gaps.db"))
    tstore = SQLiteTicketStorage(db_path=str(tmp_path / "tickets.db"))
    tool_gap = gstore.record_signal(
        GapSignalSource.NL_QUERY_UNANSWERED, "找相似武将",
        workspace_id="ws1", domain_id="d1",
        attribution={"layer": GapLayer.TOOL.value, "target_ref": "nl_engine"},
    )
    svc = GapService(storage=gstore)
    svc._ticket_service_factory = lambda: TicketService(storage=tstore)

    app = FastAPI()
    app.include_router(router)
    from odap.biz.semantic_admin.gap_pool.api import routes as R
    app.dependency_overrides[R.get_current_user] = lambda: {"sub": "alice"}
    app.dependency_overrides[R.verify_semantic_writer] = lambda: {"sub": "alice"}
    monkeypatch.setattr(R, "_gap_service_override", svc)
    return TestClient(app), gstore, tstore, tool_gap


def test_route_preview_endpoint(wired):
    client, gstore, _tstore, gap = wired
    r = client.get(f"/api/semantic-admin/gaps/{gap['id']}/route-preview")
    assert r.status_code == 200
    body = r.json()
    assert body["layer"] == "tool"
    assert body["routed_to"] == "tool_routing"
    assert body["engine"] == "nl_engine"
    # 无副作用
    assert gstore.get_gap(gap["id"])["status"] == "open"


def test_route_preview_404(wired):
    client, _g, _t, _gap = wired
    r = client.get("/api/semantic-admin/gaps/nope/route-preview")
    assert r.status_code == 404


def test_promote_endpoint_creates_ticket(wired):
    client, gstore, tstore, gap = wired
    r = client.post(f"/api/semantic-admin/gaps/{gap['id']}/promote", json={})
    assert r.status_code == 200
    body = r.json()
    assert body["routed_to"] == "tool_routing"
    assert tstore.get_ticket(body["ticket_id"])["status"] == "open"
    assert gstore.get_gap(gap["id"])["promoted_ticket_id"] == body["ticket_id"]
