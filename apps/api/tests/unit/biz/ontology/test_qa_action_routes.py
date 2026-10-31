"""F9 动作端点测试（AC-40 / AC-41 / AC-42）—— 路由层。

验证 HTTP 语义与错误契约：
    GET  /api/v1/ontology/qa/{trace_id}/actions
    POST /api/v1/ontology/qa/actions/{action_id}/approve
    POST /api/v1/ontology/qa/actions/{action_id}/execute
"""

from __future__ import annotations

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

ERROR_FIELDS = {"error_code", "message", "detail", "trace_id"}


@pytest.fixture
def client(build_pipeline, trace_repo, action_service):
    from odap.biz.core.ontology.orchestration.api import routes as qa_routes
    from odap.infra.middleware.api_error_handler import register_api_error_handler
    from odap.infra.security.jwt_auth import get_current_user

    app = FastAPI()
    app.include_router(qa_routes.router)
    register_api_error_handler(app)

    async def _user():
        return {"sub": "u-arch", "role": "admin", "roles": ["admin"],
                "ws_role": "super_admin", "workspace_id": "ws-supply"}

    app.dependency_overrides[get_current_user] = _user

    qa_routes.set_services(
        pipeline=build_pipeline(actions=action_service),
        trace_repo=trace_repo,
        actions=action_service,
    )
    with TestClient(app) as test_client:
        yield test_client
    qa_routes.reset_services()


def _ask(client, allow_actions: bool = True):
    response = client.post(
        "/api/v1/ontology/qa",
        json={
            "query": "上个季度退货率最高的三个品类是什么",
            "workspace_id": "ws-supply",
            "allow_actions": allow_actions,
        },
    )
    assert response.status_code == 200, response.text
    return response.json()["data"]


class TestSuggestedActionsInEnvelope:
    def test_default_response_exposes_readonly_actions(self, client):
        data = _ask(client, allow_actions=False)
        actions = data["suggested_actions"]
        assert actions, "AC-40：必须返回 suggested_actions"
        assert all(a["risk_level"] == "low" for a in actions)
        assert all(a["action_id"] for a in actions)
        assert all(a["requires_hitl"] is False for a in actions)

    def test_actions_allowed_includes_high_risk(self, client):
        data = _ask(client, allow_actions=True)
        risks = {a["action_type"]: a["risk_level"] for a in data["suggested_actions"]}
        assert risks.get("export_answer_wiki") == "high"
        high = [a for a in data["suggested_actions"] if a["risk_level"] == "high"]
        assert high and all(a["requires_hitl"] for a in high)


class TestActionEndpoints:
    def test_list_actions_links_to_trace(self, client):
        data = _ask(client)
        trace_id = data["trace_id"]
        response = client.get(f"/api/v1/ontology/qa/{trace_id}/actions")
        assert response.status_code == 200
        body = response.json()["data"]
        assert body["trace_id"] == trace_id
        assert {a["trace_id"] for a in body["actions"]} == {trace_id}

    def test_list_unknown_trace_returns_404(self, client):
        response = client.get(
            "/api/v1/ontology/qa/urn:odap:trace:01AAAAAAAAAAAAAAAAAAAAAAAA/actions"
        )
        assert response.status_code == 404
        body = response.json()
        assert set(body) == ERROR_FIELDS
        assert body["error_code"] == "QA_TRACE_NOT_FOUND"

    def test_high_risk_execute_without_approval_is_409(self, client):
        data = _ask(client)
        high = next(a for a in data["suggested_actions"] if a["risk_level"] == "high")
        response = client.post(
            f"/api/v1/ontology/qa/actions/{high['action_id']}/execute"
        )
        assert response.status_code == 409
        body = response.json()
        assert set(body) == ERROR_FIELDS
        assert body["error_code"] == "ACTION_HITL_REQUIRED"
        assert body["detail"]["risk_level"] == "high"

    def test_low_risk_execute_without_approval_succeeds(self, client):
        data = _ask(client)
        low = next(a for a in data["suggested_actions"] if a["risk_level"] == "low")
        response = client.post(
            f"/api/v1/ontology/qa/actions/{low['action_id']}/execute"
        )
        assert response.status_code == 200
        body = response.json()["data"]
        assert body["action"]["status"] == "executed"
        assert body["action"]["trace_id"] == data["trace_id"]

    def test_high_risk_approve_then_execute(self, client):
        data = _ask(client)
        high_risks = [a for a in data["suggested_actions"] if a["risk_level"] == "high"]
        if not high_risks:  # 未开启写动作时跳过（避免空断言）
            pytest.skip("该响应未下发高风险动作")
        high = high_risks[0]

        approve = client.post(
            f"/api/v1/ontology/qa/actions/{high['action_id']}/approve",
            json={"approved": True, "note": "架构师确认导出"},
        )
        assert approve.status_code == 200, approve.text
        assert approve.json()["data"]["status"] == "approved"

        executed = client.post(
            f"/api/v1/ontology/qa/actions/{high['action_id']}/execute"
        )
        # export_answer_wiki 本轮未实现执行路径 → 必须显式 501，不得假成功
        assert executed.status_code == 501
        assert executed.json()["error_code"] == "ACTION_EXECUTION_NOT_IMPLEMENTED"

    def test_approve_low_risk_is_409(self, client):
        data = _ask(client, allow_actions=False)
        low = data["suggested_actions"][0]
        response = client.post(
            f"/api/v1/ontology/qa/actions/{low['action_id']}/approve",
            json={"approved": True},
        )
        assert response.status_code == 409
        assert response.json()["error_code"] == "ACTION_HITL_NOT_APPLICABLE"

    def test_unknown_action_returns_404(self, client):
        response = client.post(
            "/api/v1/ontology/qa/actions/act-01J9ZK8P3Q7N2M4R5T6V7W8X9A/execute"
        )
        assert response.status_code == 404
        assert response.json()["error_code"] == "ACTION_NOT_FOUND"

    def test_decision_body_is_validated(self, client):
        data = _ask(client)
        action_id = data["suggested_actions"][0]["action_id"]
        response = client.post(
            f"/api/v1/ontology/qa/actions/{action_id}/approve",
            json={"approved": True, "surprise": 1},
        )
        assert response.status_code == 422


class TestActionProvenanceClosure:
    def test_action_and_provenance_share_trace(self, client):
        """AC-42：先取证 → 再决策 → 后行动，动作与溯源共用同一 trace_id。"""
        data = _ask(client)
        trace_id = data["trace_id"]

        low = next(a for a in data["suggested_actions"] if a["action_type"] == "open_provenance")
        executed = client.post(f"/api/v1/ontology/qa/actions/{low['action_id']}/execute")
        assert executed.status_code == 200
        assert executed.json()["data"]["result"]["trace_id"] == trace_id

        provenance = client.get(f"/api/v1/ontology/qa/{trace_id}/provenance")
        assert provenance.status_code == 200
        steps = [s["step"] for s in provenance.json()["data"]["steps"]]
        assert steps == ["intent", "map", "guard", "retrieve", "compose", "gate"]

        listed = client.get(f"/api/v1/ontology/qa/{trace_id}/actions").json()["data"]
        statuses = {a["id"]: a["status"] for a in listed["actions"]}
        assert statuses[low["action_id"]] == "executed"
