"""子项目 B：gap-regression 路由测试（状态码映射、HTTPException 透传、鉴权 override）。"""
import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from odap.biz.semantic_admin.gap_pool.regression.api import routes as rt
from odap.biz.semantic_admin.gap_pool.regression.api.routes import router
from odap.biz.semantic_admin.gap_pool.regression.runner import PairedReplayRunner
from odap.biz.semantic_admin.gap_pool.regression.service import RegressionService
from odap.infra.security.jwt_auth import get_current_user


class _AnswerAllPipeline:
    """路由测试边界桩：全部答上（replay 判定逻辑在 test_paired_replay 已真体覆盖）。"""

    async def query(self, request):
        from odap.biz.data.qa.models import QueryResponse
        return QueryResponse(answer="ok")


@pytest.fixture
def client(monkeypatch, tmp_path):
    """注入 tmp DB + 可控 pipeline 的 RegressionService override + 跳过鉴权。"""
    svc = RegressionService(
        data_dir=str(tmp_path),
        runner=PairedReplayRunner(pipeline=_AnswerAllPipeline()),
    )
    monkeypatch.setattr(rt, "_reg_service_override", svc)

    async def fake_user():
        return {"sub": "tester"}

    app = FastAPI()
    app.include_router(router)
    app.dependency_overrides[get_current_user] = fake_user
    return TestClient(app)


def test_sets_build_then_list_then_get(client):
    r = client.post("/api/semantic-admin/gap-regression/sets/build",
                    json={"workspace_id": "ws-none", "domain_id": "d1"})
    assert r.status_code == 200
    body = r.json()
    assert body["status"] == "ok"
    set_id = body["set_id"]

    r2 = client.get("/api/semantic-admin/gap-regression/sets")
    assert r2.status_code == 200
    assert any(s["id"] == set_id for s in r2.json()["items"])

    r3 = client.get(f"/api/semantic-admin/gap-regression/sets/{set_id}")
    assert r3.status_code == 200
    assert r3.json()["id"] == set_id


def test_get_missing_set_404(client):
    assert client.get("/api/semantic-admin/gap-regression/sets/nope").status_code == 404


def test_replay_missing_set_404(client):
    assert client.post(
        "/api/semantic-admin/gap-regression/sets/nope/replay").status_code == 404


def test_replay_empty_set_verdict_fail(client):
    """空集回放：fixed=0 无修复 → verdict=fail（不造 pass）。"""
    r = client.post("/api/semantic-admin/gap-regression/sets/build",
                    json={"workspace_id": "ws-none", "domain_id": "d1"})
    set_id = r.json()["set_id"]
    r2 = client.post(f"/api/semantic-admin/gap-regression/sets/{set_id}/replay")
    assert r2.status_code == 200
    body = r2.json()
    assert body["status"] == "ok"
    assert body["report"]["verdict"] == "fail"
    # 报告列表可见
    r3 = client.get("/api/semantic-admin/gap-regression/reports")
    assert r3.status_code == 200
    assert any(rp["set_id"] == set_id for rp in r3.json()["items"])


def test_get_report_detail_and_404(client):
    r = client.post("/api/semantic-admin/gap-regression/sets/build",
                    json={"workspace_id": "ws-none"})
    set_id = r.json()["set_id"]
    rep = client.post(
        f"/api/semantic-admin/gap-regression/sets/{set_id}/replay").json()["report"]
    r2 = client.get(f"/api/semantic-admin/gap-regression/reports/{rep['id']}")
    assert r2.status_code == 200
    assert r2.json()["id"] == rep["id"]
    assert client.get(
        "/api/semantic-admin/gap-regression/reports/nope").status_code == 404


def test_build_with_filters_passes_through(client):
    r = client.post("/api/semantic-admin/gap-regression/sets/build",
                    json={"status": "open", "workspace_id": "ws-x",
                          "domain_id": "d1", "min_heat": 2})
    assert r.status_code == 200
    assert r.json()["status"] == "ok"
