import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from odap.biz.semantic_admin.drift_scan.api.routes import router
from odap.biz.semantic_admin.drift_scan.services import DriftService
from odap.biz.semantic_admin.drift_scan.storage import SQLiteDriftStorage


@pytest.fixture
def client(tmp_path, monkeypatch):
    store = SQLiteDriftStorage(db_path=str(tmp_path / "drift.db"))
    app = FastAPI()
    app.include_router(router)
    from odap.biz.semantic_admin.drift_scan.api import routes as R
    app.dependency_overrides[R.get_current_user] = lambda: {"sub": "alice", "role": "admin"}
    monkeypatch.setattr(R, "_drift_service_override", DriftService(storage=store))
    store.save_report_with_findings(
        {"id": "r1", "trigger": "manual", "status": "ok", "started_at": "2026-01-01T00:00:00",
         "scope_json": {}, "source_errors_json": {}, "counts_json": {"forks": 0, "evolutions": 0}}, [])
    return TestClient(app)


def test_list_reports(client):
    r = client.get("/api/semantic-admin/drift/reports")
    assert r.status_code == 200
    assert r.json()["total"] >= 1


def test_get_report_404(client):
    r = client.get("/api/semantic-admin/drift/reports/nope")
    assert r.status_code == 404


def test_get_report_ok(client):
    r = client.get("/api/semantic-admin/drift/reports/r1")
    assert r.status_code == 200
    assert "report" in r.json()


def test_latest(client):
    r = client.get("/api/semantic-admin/drift/reports/latest")
    assert r.status_code == 200
