"""T7 / G6 回归：agent 决策链隔离收口 + 反馈回填取对字段

两条永久回归：
1. **agent 决策链不得凭 ID 越权**：原 `GET /api/agent/decisions/{id}` 只按主键直取
   （IDOR），`GET ""` 在 `workspace_id` 为 falsy 时返回**全空间**数据。
   收口后：跨空间一律按"不存在"处理（404 / not found），workspace 声明缺失 422。
2. **`feedback_loop` 取错字段**：`decision_id=action_record.get('agent_id')` 让反馈
   永远挂错决策，必须取 `decision_id`。
"""

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from odap.biz.core.agent.models.decision_chain import DecisionPhase
from odap.biz.core.agent.services.decision_service import (
    DecisionScopeError,
    DecisionService,
)
from odap.infra.security.jwt_auth import get_current_user


@pytest.fixture
def service() -> DecisionService:
    instance = DecisionService()
    instance._decisions.clear()  # 进程级单例，逐用例重置
    return instance


def _create(service: DecisionService, workspace_id: str, task_id: str = "t1") -> str:
    result = service.create_decision(task_id=task_id, workspace_id=workspace_id)
    return result["decision_id"]


# ---------------- 服务层：归属校验 ----------------


def test_create_decision_requires_workspace(service):
    with pytest.raises(ValueError, match="workspace_id"):
        service.create_decision(task_id="t1", workspace_id="")


def test_get_decision_rejects_cross_workspace(service):
    decision_id = _create(service, "ws-a")
    with pytest.raises(DecisionScopeError):
        service.get_decision(decision_id, "ws-b")


def test_get_decision_returns_own_workspace(service):
    decision_id = _create(service, "ws-a")
    assert service.get_decision(decision_id, "ws-a")["decision_id"] == decision_id


def test_get_decision_chain_rejects_cross_workspace(service):
    decision_id = _create(service, "ws-a")
    with pytest.raises(DecisionScopeError):
        service.get_decision_chain(decision_id, "ws-b")


def test_record_step_rejects_cross_workspace(service):
    decision_id = _create(service, "ws-a")
    with pytest.raises(DecisionScopeError):
        service.record_step(
            decision_id=decision_id,
            phase=DecisionPhase.OBSERVE,
            description="外部调用",
            workspace_id="ws-b",
        )


def test_record_step_binds_workspace_on_new_chain(service):
    result = service.record_step(
        decision_id="uuid-style-id",
        phase=DecisionPhase.ORIENT,
        description="确认漂移集中在供应商主体",
        workspace_id="ws-a",
    )
    assert result["decision_id"] == "uuid-style-id"
    assert service.get_decision_chain("uuid-style-id", "ws-a")["decision_id"] == "uuid-style-id"


def test_list_decisions_filters_by_workspace(service):
    _create(service, "ws-a", "a1")
    _create(service, "ws-a", "a2")
    _create(service, "ws-b", "b1")
    result = service.list_decisions("ws-a")
    assert result["total"] == 2
    assert all(d["workspace_id"] == "ws-a" for d in result["decisions"])


def test_list_decisions_rejects_empty_workspace(service):
    # 拒绝"空即不过滤"：这是原来跨空间泄露的根因
    with pytest.raises(ValueError, match="workspace_id"):
        service.list_decisions("")


# ---------------- 路由层 ----------------


@pytest.fixture
def client(service) -> TestClient:
    from odap.biz.core.agent.api.decision_routes import router

    app = FastAPI()
    app.include_router(router)

    async def _user():
        return {"sub": "u1", "role": "analyst", "ws_id": "ws-a"}

    app.dependency_overrides[get_current_user] = _user
    return TestClient(app)


def test_route_get_decision_cross_workspace_is_404(client, service):
    decision_id = _create(service, "ws-b")  # 别人的空间
    assert client.get(f"/api/agent/decisions/{decision_id}").status_code == 404


def test_route_get_decision_chain_cross_workspace_is_404(client, service):
    decision_id = _create(service, "ws-b")
    assert client.get(f"/api/agent/decisions/{decision_id}/chain").status_code == 404


def test_route_get_decision_own_workspace_ok(client, service):
    decision_id = _create(service, "ws-a")
    resp = client.get(f"/api/agent/decisions/{decision_id}")
    assert resp.status_code == 200
    assert resp.json()["decision_id"] == decision_id


def test_route_list_ignores_client_workspace_param(client, service):
    _create(service, "ws-a", "a1")
    _create(service, "ws-b", "b1")
    resp = client.get("/api/agent/decisions", params={"workspace_id": "ws-b"})
    assert resp.status_code == 200
    body = resp.json()
    assert body["total"] == 1
    assert all(d["workspace_id"] == "ws-a" for d in body["decisions"])


def test_route_missing_workspace_claim_is_422(client):
    async def _user_without_ws():
        return {"sub": "u1", "role": "analyst"}

    client.app.dependency_overrides[get_current_user] = _user_without_ws
    assert client.get("/api/agent/decisions").status_code == 422
    assert client.get("/api/agent/decisions/whatever").status_code == 422


def test_route_record_step_cross_workspace_is_404(client, service):
    decision_id = _create(service, "ws-b")
    resp = client.post(
        f"/api/agent/decisions/{decision_id}/steps",
        params={"phase": "observe", "description": "x"},
    )
    assert resp.status_code == 404


# ---------------- 反馈回填取对字段 ----------------


def test_feedback_collect_uses_decision_id():
    from odap.biz.decision.action_service.feedback_loop import FeedbackCollector

    feedback = FeedbackCollector().collect(
        {
            "action_record_id": "act_1",
            "decision_id": "dec_real",
            "agent_id": "agent_wrong",
            "execution_result": {"success": True},
        }
    )
    assert feedback.decision_id == "dec_real"
