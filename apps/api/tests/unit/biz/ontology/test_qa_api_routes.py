"""QA 路由层测试（AC-25 / AC-26 / AC-28 / AC-56）。

验证两点：
1. 空 query 与未知 trace 走统一错误契约 `{error_code, message, detail, trace_id}`；
2. 正常问答返回信封，`trace_id` 可用于查询溯源。
"""

from __future__ import annotations

import re

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

TRACE_PATTERN = re.compile(r"^urn:odap:trace:[0-9A-HJKMNP-TV-Z]{26}$")


@pytest.fixture
def client(build_pipeline, trace_repo):
    from odap.biz.core.ontology.orchestration.api import routes as qa_routes
    from odap.infra.middleware.api_error_handler import register_api_error_handler
    from odap.infra.security.jwt_auth import get_current_user

    app = FastAPI()
    app.include_router(qa_routes.router)
    register_api_error_handler(app)

    async def _user():
        return {"sub": "u-analyst", "roles": ["analyst"], "workspace_id": "ws-supply"}

    app.dependency_overrides[get_current_user] = _user

    qa_routes.set_services(pipeline=build_pipeline(), trace_repo=trace_repo)
    with TestClient(app) as test_client:
        yield test_client
    qa_routes.reset_services()


def _ask(client, **payload):
    body = {"query": "上个季度退货率最高的三个品类是什么", "workspace_id": "ws-supply"}
    body.update(payload)
    return client.post("/api/v1/ontology/qa", json=body)


class TestQaEndpoint:
    def test_answered_envelope(self, client):
        response = _ask(client)
        assert response.status_code == 200
        body = response.json()
        assert body["code"] == 0
        data = body["data"]
        assert data["status"] == "answered"
        assert TRACE_PATTERN.match(data["trace_id"])
        assert data["intent"]["intent_type"] == "metric_query"
        assert data["contract_ok"] is True
        assert data["citations"], "答案必须带可解析引用"

    def test_empty_query_returns_400_with_error_contract(self, client):
        response = _ask(client, query="   ")
        assert response.status_code == 400
        body = response.json()
        assert set(body) == {"error_code", "message", "detail", "trace_id"}
        assert body["error_code"] == "QA_QUERY_REQUIRED"
        assert body["detail"] == {"field": "query"}
        assert TRACE_PATTERN.match(body["trace_id"])

    def test_missing_query_field_also_400(self, client):
        response = client.post("/api/v1/ontology/qa", json={"workspace_id": "ws-supply"})
        assert response.status_code == 400
        assert response.json()["error_code"] == "QA_QUERY_REQUIRED"

    def test_unknown_mode_is_rejected_by_schema(self, client):
        response = _ask(client, mode="telepathy")
        assert response.status_code == 422

    def test_unknown_field_is_rejected(self, client):
        response = _ask(client, surprise="x")
        assert response.status_code == 422


class TestProvenanceEndpoint:
    def test_provenance_roundtrip_via_api(self, client):
        trace_id = _ask(client).json()["data"]["trace_id"]
        response = client.get(f"/api/v1/ontology/qa/{trace_id}/provenance")
        assert response.status_code == 200
        data = response.json()["data"]
        assert data["trace_id"] == trace_id
        assert [s["step"] for s in data["steps"]] == [
            "intent", "map", "guard", "retrieve", "compose", "gate"
        ]
        assert data["tbox_version"].startswith("sha256:")

    def test_unknown_trace_returns_404(self, client):
        response = client.get(
            "/api/v1/ontology/qa/urn:odap:trace:01J9ZK8P3Q7N2M4R5T6V7W8X9A/provenance"
        )
        assert response.status_code == 404
        body = response.json()
        assert body["error_code"] == "QA_TRACE_NOT_FOUND"
        assert body["detail"]["trace_id"].startswith("urn:odap:trace:")

    def test_clarify_trace_is_queryable(self, client):
        trace_id = _ask(client, query="你好").json()["data"]["trace_id"]
        data = client.get(f"/api/v1/ontology/qa/{trace_id}/provenance").json()["data"]
        assert len(data["steps"]) == 6
