import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from odap.biz.semantic_admin.gap_pool.api.routes import router
from odap.biz.semantic_admin.gap_pool.services import GapService
from odap.biz.semantic_admin.gap_pool.storage import SQLiteGapStorage
from odap.biz.semantic_admin.gap_pool.models import GapSignalSource


@pytest.fixture
def client(tmp_path, monkeypatch):
    store = SQLiteGapStorage(db_path=str(tmp_path / "concept_gaps.db"))
    store.record_signal(GapSignalSource.TERM_RESOLVE_MISS, "势力",
                        workspace_id="ws1", domain_id="d1")
    app = FastAPI()
    app.include_router(router)
    # 覆盖鉴权与 service 单例
    from odap.biz.semantic_admin.gap_pool.api import routes as R
    app.dependency_overrides[R.get_current_user] = lambda: {"sub": "alice", "role": "admin"}
    app.dependency_overrides[R.verify_semantic_writer] = lambda: {"sub": "alice"}
    # 终审 n2：用 monkeypatch 设置 override，测试结束自动还原，避免模块级状态泄漏到后续用例
    monkeypatch.setattr(R, "_gap_service_override", GapService(storage=store))
    return TestClient(app)


def test_list_gaps(client):
    r = client.get("/api/semantic-admin/gaps/")
    assert r.status_code == 200
    body = r.json()
    assert body["total"] >= 1


def test_get_gap_404(client):
    r = client.get("/api/semantic-admin/gaps/nope")
    assert r.status_code == 404


def test_stats(client):
    r = client.get("/api/semantic-admin/gaps/stats")
    assert r.status_code == 200
    assert "by_status" in r.json()


def test_httpexception_passthrough_not_swallowed(client):
    # 详情 404 必须原样透传，不能被兜底成 500
    r = client.get("/api/semantic-admin/gaps/does-not-exist")
    assert r.status_code == 404
