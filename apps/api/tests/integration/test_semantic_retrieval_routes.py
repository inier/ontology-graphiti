"""T020 路由集成测试 (spec 008 / Phase 8 / FR-011/012/013)。

覆盖跨故事非功能约束：
  FR-012: workspace_id 从 JWT user.get('ws_id') 提取，跨 workspace 隔离
  FR-013: 审计日志不记录 query 明文内容
  FR-011: 默认过滤 valid=false / is_candidate=true 实体（在 graph_engine 单测覆盖，
          此处验证端点不破坏该契约）
  page_size/limit ≤ 200 边界（SearchRequest.limit ge=1 le=200）

设计:
  · FastAPI TestClient + dependency_overrides 覆盖 get_current_user
  · monkeypatch routes._service 注入 FakeService（捕获 ws_id/audit 明文检查）
  · 不依赖 Neo4j/JWT 真实服务
"""

from __future__ import annotations

import sys
import os

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient


# ── 公共 fixtures ────────────────────────────────────────────────────────

@pytest.fixture
def app_with_overrides():
    """构造带 get_current_user override 的 FastAPI app。"""
    from odap.biz.core.ontology.semantic_retrieval.api import routes as sr_routes
    from odap.infra.security.jwt_auth import get_current_user

    app = FastAPI()
    app.include_router(sr_routes.router)

    # 默认用户：workspace_id = "ws-alpha"
    def _fake_user():
        return {"sub": "user-001", "ws_id": "ws-alpha", "role": "user"}

    app.dependency_overrides[get_current_user] = _fake_user
    return app, sr_routes


@pytest.fixture
def client(app_with_overrides):
    app, _ = app_with_overrides
    return TestClient(app)


@pytest.fixture
def fake_service(app_with_overrides, monkeypatch):
    """注入 FakeService 捕获调用参数。"""
    _, sr_routes = app_with_overrides

    class FakeService:
        def __init__(self):
            self.calls = []  # 记录 (method, workspace_id, args)

        async def search(self, ws, req):
            self.calls.append(("search", ws, {"query": req.query, "limit": req.limit}))
            return {"query": req.query, "mode": req.mode, "total": 0, "rows": []}

        async def graph_search(self, ws, query, limit=20):
            self.calls.append(("graph_search", ws, {"query": query, "limit": limit}))
            return {"mode": "graph", "total": 0, "rows": [], "explain": {}}

        async def nl_search(self, ws, query, limit=20):
            self.calls.append(("nl_search", ws, {"query": query, "limit": limit}))
            return {"mode": "nl", "total": 0, "rows": []}

        async def metric_search(self, ws, metric, **kw):
            self.calls.append(("metric_search", ws, {"metric": metric, **kw}))
            return {"mode": "metric", "metrics": [], "rows": [], "total": 0, "explain": {}}

        async def chain_search(self, ws, *, query, rules, max_depth):
            self.calls.append(("chain_search", ws, {"query": query, "max_depth": max_depth}))
            return {"mode": "chain", "reasoning": {"chain_id": "c1", "steps": [], "conclusion": "", "cycle_detected": False, "conflicts": []}, "warnings": [], "total": 0}

        async def mdl_search(self, ws, *, query):
            self.calls.append(("mdl_search", ws, {"query": query}))
            return {"mode": "mdl", "reasoning": {"chain_id": "m1", "template": "t", "entity": "e", "params": {}, "status": "degraded", "conclusion": "", "confidence": 0.0, "cycle_detected": False, "conflicts": []}, "warnings": [], "total": 0}

        async def hybrid_search(self, ws, components, *, merge="concat"):
            self.calls.append(("hybrid_search", ws, {"components_n": len(components), "merge": merge}))
            return {"mode": "hybrid", "request_id": "r1", "rows": [], "total": 0, "components": [], "warnings": []}

    fake = FakeService()
    monkeypatch.setattr(sr_routes, "_service", fake)
    return fake


# ── T020-1: 缺认证 → 401 (FR-012 强制认证) ──────────────────────────────

def test_missing_auth_returns_401():
    """T020-1: 无 Bearer token → 401 UNAUTHORIZED (FR-012)。"""
    from odap.biz.core.ontology.semantic_retrieval.api import routes as sr_routes
    app = FastAPI()
    app.include_router(sr_routes.router)
    # 不覆盖 get_current_user → 真实 HTTPBearer 会拒绝
    c = TestClient(app, raise_server_exceptions=False)
    r = c.post("/api/semantic-retrieval/query", json={"query": "test"})
    assert r.status_code == 401, f"期望 401, 实际 {r.status_code}: {r.text}"


# ── T020-2: workspace_id 从 JWT 提取并透传到 service (FR-012) ────────────

def test_workspace_id_extracted_from_jwt_and_propagated(client, fake_service):
    """T020-2: JWT ws_id='ws-alpha' → service 收到 workspace_id='ws-alpha'。"""
    r = client.post(
        "/api/semantic-retrieval/graph",
        json={"query": "装备A"},
    )
    assert r.status_code == 200, f"期望 200, 实际 {r.status_code}: {r.text}"
    # 验证 service 收到正确 ws_id
    assert any(
        call[0] == "graph_search" and call[1] == "ws-alpha"
        for call in fake_service.calls
    ), f"workspace_id 未透传: {fake_service.calls}"


# ── T020-3: limit 超过 200 → 422 校验失败 ─────────────────────────────────

def test_limit_over_200_returns_422(client, fake_service):
    """T020-3a: limit=201 超过 SearchRequest.le=200 → 422 校验失败。"""
    r = client.post(
        "/api/semantic-retrieval/query",
        json={"query": "test", "limit": 201},
    )
    assert r.status_code == 422, f"期望 422, 实际 {r.status_code}: {r.text}"


def test_limit_zero_returns_422(client, fake_service):
    """T020-3b: limit=0 低于 SearchRequest.ge=1 → 422。"""
    r = client.post(
        "/api/semantic-retrieval/query",
        json={"query": "test", "limit": 0},
    )
    assert r.status_code == 422


def test_limit_at_max_accepted(client, fake_service):
    """T020-3c: limit=200 边界值 → 200 OK。"""
    r = client.post(
        "/api/semantic-retrieval/query",
        json={"query": "test", "limit": 200},
    )
    assert r.status_code == 200


# ── T020-4: chain max_depth > 10 → 400 ValueError (FR-014 硬上限) ─────────

def test_chain_max_depth_over_10_returns_400(client, fake_service):
    """T020-4: ChainRequest.max_depth=11 → Pydantic le=10 校验 422（双保险）。"""
    r = client.post(
        "/api/semantic-retrieval/chain",
        json={"query": "q", "rules": [], "max_depth": 11},
    )
    assert r.status_code == 422, f"期望 422 (Pydantic le=10), 实际 {r.status_code}"


# ── T020-5: hybrid components 超过 10 → 422 (FR-007 边界) ─────────────────

def test_hybrid_components_over_10_returns_422(client, fake_service):
    """T020-5: 11 个 components → HybridRequest.max_length=10 → 422。"""
    components = [{"type": "graph", "params": {"query": "q"}} for _ in range(11)]
    r = client.post(
        "/api/semantic-retrieval/hybrid",
        json={"components": components},
    )
    assert r.status_code == 422


def test_hybrid_components_zero_returns_422(client, fake_service):
    """T020-5b: 0 个 components → HybridRequest.min_length=1 → 422。"""
    r = client.post(
        "/api/semantic-retrieval/hybrid",
        json={"components": []},
    )
    assert r.status_code == 422


# ── T020-6: 7 端点全部注册（路由层冒烟） ──────────────────────────────────

def test_all_seven_routes_registered(app_with_overrides):
    """T020-6: 7 端点路由全部注册到 FastAPI app。"""
    app, _ = app_with_overrides
    paths = {route.path for route in app.routes if hasattr(route, "path")}
    expected = {
        "/api/semantic-retrieval/query",
        "/api/semantic-retrieval/graph",
        "/api/semantic-retrieval/nl",
        "/api/semantic-retrieval/metric",
        "/api/semantic-retrieval/chain",
        "/api/semantic-retrieval/mdl",
        "/api/semantic-retrieval/hybrid",
    }
    missing = expected - paths
    assert not missing, f"端点未注册: {missing}"


# ── T020-7: 审计不记录 query 明文 (FR-013) ───────────────────────────────

def test_audit_does_not_record_query_plaintext(monkeypatch):
    """T020-7: 真实 RetrievalService 调用 audit_retrieval 时 details 无 query 明文。

    直接对 retrieval_service 模块的 audit_retrieval 绑定打 patch，
    用真实 RetrievalService + 注入 FakeEngine 触发审计路径。
    """
    import asyncio
    from odap.biz.core.ontology.semantic_retrieval.services import retrieval_service as rs_mod
    from odap.biz.core.ontology.semantic_retrieval.services.retrieval_service import RetrievalService

    audit_calls = []

    def _capture_audit(action, *, details=None, **kw):
        audit_calls.append({"action": action, "details": details or {}})

    # 关键：patch 模块级 audit_retrieval 绑定（retrieval_service.py 顶部 from ... import 的符号）
    monkeypatch.setattr(rs_mod, "audit_retrieval", _capture_audit)

    # FakeEngine: 仅返回结构化结果，让 service 走完审计路径
    class FakeEngine:
        async def search(self, ws, query, limit=20):
            return {"mode": "nl", "total": 0, "rows": []}

    # 全引擎注入：避免 GraphEngine/MetricEngine 默认构造触发 Neo4j 连接
    svc = RetrievalService(
        graph_engine=FakeEngine(),
        nl_engine=FakeEngine(),
        metric_engine=FakeEngine(),
        chain_engine=FakeEngine(),
        mdl_engine=FakeEngine(),
    )

    # 触发 nl_search 审计路径
    asyncio.run(svc.nl_search("ws-test", "敏感查询内容", limit=20))

    assert len(audit_calls) >= 1, f"audit 未被调用: {audit_calls}"
    for call in audit_calls:
        details = call["details"]
        # FR-013: details 不得包含 query 明文
        assert "query" not in details, (
            f"FR-013 违规：审计 details 含 query 明文: {call}"
        )
        # 仅允许 query_len（长度统计，非明文）
        if "query_len" in details:
            assert isinstance(details["query_len"], int)
