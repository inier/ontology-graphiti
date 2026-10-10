"""TDD：工单 API 端点（子项目 D E-12）——7 端点状态码/鉴权/异常透传。"""
from __future__ import annotations

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from odap.biz.semantic_admin.routing_tickets.api import routes as R
from odap.biz.semantic_admin.routing_tickets.services.ticket_service import TicketService
from odap.biz.semantic_admin.routing_tickets.storage import SQLiteTicketStorage


@pytest.fixture
def env(tmp_path, monkeypatch):
    svc = TicketService(storage=SQLiteTicketStorage(db_path=str(tmp_path / "t.db")))
    t = svc.create_from_gap({"id": "g1", "expression": "司马懿",
                             "scope_key": "ws::sanguo"}, actor="alice",
                            engine="nl_engine")["ticket"]
    app = FastAPI()
    app.include_router(R.router)
    app.dependency_overrides[R.get_current_user] = lambda: {"sub": "alice"}
    app.dependency_overrides[R.verify_semantic_writer] = lambda: {"sub": "alice"}
    monkeypatch.setattr(R, "_svc_override", svc)
    return TestClient(app), svc, t["id"]


def test_list(env):
    client, _, _ = env
    r = client.get("/api/semantic-admin/routing-tickets/")
    assert r.status_code == 200
    assert r.json()["total"] == 1


def test_stats(env):
    client, _, _ = env
    r = client.get("/api/semantic-admin/routing-tickets/stats")
    assert r.status_code == 200
    assert "by_status" in r.json()


def test_detail_and_404(env):
    client, _, tid = env
    assert client.get(f"/api/semantic-admin/routing-tickets/{tid}").status_code == 200
    assert client.get("/api/semantic-admin/routing-tickets/nope").status_code == 404


def test_events(env):
    client, _, tid = env
    r = client.get(f"/api/semantic-admin/routing-tickets/{tid}/events")
    assert r.status_code == 200
    assert r.json()["events"][0]["event_type"] == "created"


def test_assign_and_transition(env):
    client, _, tid = env
    r = client.post(f"/api/semantic-admin/routing-tickets/{tid}/assign",
                    json={"assignee": "bob", "priority": "P0"})
    assert r.status_code == 200
    assert r.json()["ticket"]["status"] == "assigned"
    r2 = client.post(f"/api/semantic-admin/routing-tickets/{tid}/transition",
                     json={"to_status": "in_progress"})
    assert r2.status_code == 200


def test_invalid_transition_409(env):
    client, _, tid = env
    r = client.post(f"/api/semantic-admin/routing-tickets/{tid}/transition",
                    json={"to_status": "resolved"})   # open→resolved 非法
    assert r.status_code == 409


def test_comment(env):
    client, _, tid = env
    r = client.post(f"/api/semantic-admin/routing-tickets/{tid}/comment",
                    json={"note": "hi"})
    assert r.status_code == 200


def test_assign_requires_writer(env):
    client, _, tid = env
    client.app.dependency_overrides.pop(R.verify_semantic_writer, None)
    r = client.post(f"/api/semantic-admin/routing-tickets/{tid}/assign",
                    json={"assignee": "bob"})
    assert r.status_code in (401, 403)
