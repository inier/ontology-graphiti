"""Agent API 路由层单元测试

覆盖 odap/biz/core/agent/api/routes.py：
- POST /api/agent/dispatch — 意图分派
- GET  /api/agent/tasks/{task_id} — 任务状态查询
- GET  /api/agent/tasks/{task_id}/chain — 决策链查询
- POST /api/agent/swarm/configure — Swarm 配置
- POST /api/agent/orchestrate — 统一编排

验证点（AGENTS.md 规则 3）：
- 路由层 except HTTPException: raise 透传
- HTTP 状态码映射（200/400/404/500）
- 请求/响应 schema 验证
- 服务层错误返回 {"status": "error"} 时路由翻译为 HTTPException
"""
from __future__ import annotations

import asyncio
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient


# ============================================================
# Fixtures
# ============================================================


def _build_app():
    """构建仅含 agent 路由的 FastAPI 应用。"""
    from odap.biz.core.agent.api.routes import router
    from odap.infra.security.jwt_auth import get_current_user

    app = FastAPI()
    app.include_router(router)

    async def _mock_user():
        return {"sub": "u-test", "role": "admin", "ws_id": "ws-1", "ws_role": "owner"}

    app.dependency_overrides[get_current_user] = _mock_user
    return app


@pytest.fixture
def client():
    """创建 TestClient，mock 掉 swarm/orchestrator 单例。"""
    app = _build_app()
    with TestClient(app) as c:
        yield c
    app.dependency_overrides.clear()


@pytest.fixture
def mock_swarm():
    """Mock _get_swarm 返回的 DomainSwarm 实例。"""
    swarm = MagicMock()
    swarm.dispatch_intent = AsyncMock(
        return_value={
            "task_id": "task-001",
            "assigned_agent": "analyst",
            "confidence": 0.92,
            "routing_source": "rule",
            "plan": [],
            "status": "dispatched",
        }
    )
    swarm.get_task_status = AsyncMock(
        return_value={
            "task_id": "task-001",
            "status": "completed",
            "phases_completed": ["plan", "execute"],
        }
    )
    swarm.get_decision_chain = AsyncMock(
        return_value={
            "task_id": "task-001",
            "chain": [{"phase": "plan", "result": "ok"}],
            "final_decision": {"action": "approve"},
        }
    )
    swarm.configure_swarm = AsyncMock(
        return_value={"status": "ok", "configured": True}
    )
    with patch("odap.biz.core.agent.api.routes._get_swarm", return_value=swarm):
        yield swarm


@pytest.fixture
def mock_orchestrator():
    """Mock _get_orchestrator 返回的 AgentOrchestrator 实例。"""
    orch = MagicMock()
    orch.dispatch = AsyncMock(
        return_value={
            "result_id": "r-001",
            "mode": "swarm",
            "answer": "test answer",
            "reasoning_chain": [],
            "sources": [],
            "metadata": {},
        }
    )
    with patch(
        "odap.biz.core.agent.api.routes._get_orchestrator", return_value=orch
    ):
        yield orch


# ============================================================
# 1. POST /api/agent/dispatch
# ============================================================


class TestDispatchIntent:
    """意图分派端点。"""

    def test_dispatch_success(self, client, mock_swarm):
        """成功分派返回 200 与任务信息。"""
        resp = client.post(
            "/api/agent/dispatch",
            json={"intent": "分析销售数据", "workspace_id": "ws-1"},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["task_id"] == "task-001"
        assert data["assigned_agent"] == "analyst"
        assert data["confidence"] == 0.92
        mock_swarm.dispatch_intent.assert_awaited_once()

    def test_dispatch_missing_intent_returns_422(self, client, mock_swarm):
        """缺少必填字段 intent 返回 422。"""
        resp = client.post("/api/agent/dispatch", json={"workspace_id": "ws-1"})
        assert resp.status_code == 422

    def test_dispatch_internal_error_returns_500(self, client, mock_swarm):
        """服务层抛异常时返回 500（HTTPException 透传验证）。"""
        mock_swarm.dispatch_intent = AsyncMock(side_effect=RuntimeError("boom"))
        resp = client.post(
            "/api/agent/dispatch",
            json={"intent": "x"},
        )
        assert resp.status_code == 500
        assert "boom" in resp.json()["detail"]


# ============================================================
# 2. GET /api/agent/tasks/{task_id}
# ============================================================


class TestGetTaskStatus:
    """任务状态查询端点。"""

    def test_get_task_success(self, client, mock_swarm):
        """成功查询返回 200。"""
        resp = client.get("/api/agent/tasks/task-001")
        assert resp.status_code == 200
        data = resp.json()
        assert data["task_id"] == "task-001"
        assert data["status"] == "completed"

    def test_get_task_not_found_returns_404(self, client, mock_swarm):
        """服务层返回 status=error 时翻译为 404。"""
        mock_swarm.get_task_status = AsyncMock(
            return_value={"status": "error", "message": "not found"}
        )
        resp = client.get("/api/agent/tasks/missing")
        assert resp.status_code == 404
        assert "not found" in resp.json()["detail"]

    def test_get_task_internal_error_returns_500(self, client, mock_swarm):
        """异常时返回 500。"""
        mock_swarm.get_task_status = AsyncMock(side_effect=ValueError("db down"))
        resp = client.get("/api/agent/tasks/task-001")
        assert resp.status_code == 500


# ============================================================
# 3. GET /api/agent/tasks/{task_id}/chain
# ============================================================


class TestGetDecisionChain:
    """决策链查询端点。"""

    def test_get_chain_success(self, client, mock_swarm):
        """成功查询返回 200 与决策链。"""
        resp = client.get("/api/agent/tasks/task-001/chain")
        assert resp.status_code == 200
        data = resp.json()
        assert data["task_id"] == "task-001"
        assert len(data["chain"]) == 1
        assert data["final_decision"]["action"] == "approve"

    def test_get_chain_not_found_returns_404(self, client, mock_swarm):
        """status=error 时翻译为 404。"""
        mock_swarm.get_decision_chain = AsyncMock(
            return_value={"status": "error", "message": "no chain"}
        )
        resp = client.get("/api/agent/tasks/missing/chain")
        assert resp.status_code == 404


# ============================================================
# 4. POST /api/agent/swarm/configure
# ============================================================


class TestConfigureSwarm:
    """Swarm 配置端点。"""

    def test_configure_success(self, client, mock_swarm):
        """成功配置返回 200。"""
        resp = client.post(
            "/api/agent/swarm/configure",
            json={
                "agent_roles": {"analyst": "data"},
                "routing_rules": [{"when": "x", "then": "y"}],
            },
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "ok"

    def test_configure_empty_body_returns_200(self, client, mock_swarm):
        """空请求体（字段均可选）返回 200。"""
        resp = client.post("/api/agent/swarm/configure", json={})
        assert resp.status_code == 200

    def test_configure_internal_error_returns_500(self, client, mock_swarm):
        """异常时返回 500。"""
        mock_swarm.configure_swarm = AsyncMock(side_effect=RuntimeError("cfg fail"))
        resp = client.post("/api/agent/swarm/configure", json={})
        assert resp.status_code == 500


# ============================================================
# 5. POST /api/agent/orchestrate
# ============================================================


class TestOrchestrate:
    """统一编排端点。"""

    def test_orchestrate_success(self, client, mock_orchestrator):
        """成功编排返回 200。"""
        resp = client.post(
            "/api/agent/orchestrate",
            json={"query": "分析销售", "workspace_id": "ws-1", "mode": "auto"},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["result_id"] == "r-001"
        assert data["answer"] == "test answer"

    def test_orchestrate_missing_query_returns_422(self, client, mock_orchestrator):
        """缺少必填字段 query 返回 422。"""
        resp = client.post(
            "/api/agent/orchestrate",
            json={"workspace_id": "ws-1"},
        )
        assert resp.status_code == 422

    def test_orchestrate_internal_error_returns_500(self, client, mock_orchestrator):
        """异常时返回 500。"""
        mock_orchestrator.dispatch = AsyncMock(side_effect=RuntimeError("orch fail"))
        resp = client.post(
            "/api/agent/orchestrate",
            json={"query": "x"},
        )
        assert resp.status_code == 500


# ============================================================
# 6. Schema 验证
# ============================================================


class TestAgentSchemas:
    """Agent 请求/响应 schema 验证。"""

    def test_dispatch_request_defaults(self):
        """DispatchRequest 默认值正确。"""
        from odap.biz.core.agent.api.schemas import DispatchRequest

        req = DispatchRequest(intent="x")
        assert req.intent == "x"
        assert req.context == {}  # default_factory
        assert req.workspace_id is None

    def test_orchestrate_request_defaults(self):
        """OrchestrateRequest 默认值正确。"""
        from odap.biz.core.agent.api.schemas import OrchestrateRequest

        req = OrchestrateRequest(query="x")
        assert req.query == "x"
        assert req.user_id == "anonymous"
        assert req.workspace_id == "default"
        assert req.mode == "auto"
        assert req.session_id is None

    def test_swarm_config_request_optional_fields(self):
        """SwarmConfigRequest 所有字段可选。"""
        from odap.biz.core.agent.api.schemas import SwarmConfigRequest

        req = SwarmConfigRequest()
        assert req.agent_roles is None
        assert req.routing_rules is None
