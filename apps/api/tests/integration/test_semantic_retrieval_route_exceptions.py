"""T021 G-7 路由异常回归测试 (spec 008 / Phase 8 质量门)。

G-7 定义：每个端点遇引擎异常时必须返回 HTTP 500 + 不崩溃服务器。
覆盖 routes.py 中所有 7 个端点的 `except Exception` 兜底分支。

设计:
  · FakeService 各方法抛 RuntimeError 模拟引擎故障
  · TestClient raise_server_exceptions=False 避免pytest捕获500
  · 断言 status_code == 500 + 响应体含 detail 字段
"""

from __future__ import annotations

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient


@pytest.fixture
def raising_client(monkeypatch):
    """构造 7 端点 app + 注入各方法抛异常的 FakeService。"""
    from odap.biz.core.ontology.semantic_retrieval.api import routes as sr_routes
    from odap.infra.security.jwt_auth import get_current_user

    app = FastAPI()
    app.include_router(sr_routes.router)
    app.dependency_overrides[get_current_user] = lambda: {"sub": "u1", "ws_id": "ws-x"}

    class RaisingService:
        async def search(self, ws, req):
            raise RuntimeError("engine boom")
        async def graph_search(self, ws, q, limit=20):
            raise RuntimeError("graph boom")
        async def nl_search(self, ws, q, limit=20):
            raise RuntimeError("nl boom")
        async def metric_search(self, ws, metric, **kw):
            raise RuntimeError("metric boom")
        async def chain_search(self, ws, *, query, rules, max_depth):
            raise RuntimeError("chain boom")
        async def mdl_search(self, ws, *, query):
            raise RuntimeError("mdl boom")
        async def hybrid_search(self, ws, components, *, merge="concat"):
            raise RuntimeError("hybrid boom")

    monkeypatch.setattr(sr_routes, "_service", RaisingService())
    return TestClient(app, raise_server_exceptions=False)


# ── G-7-1 ~ G-7-7: 7 端点遇引擎异常 → 500 不崩服务器 ─────────────────────

def test_g7_query_engine_exception_returns_500(raising_client):
    """G-7-1: /query 引擎异常 → 500。"""
    r = raising_client.post("/api/semantic-retrieval/query", json={"query": "x"})
    assert r.status_code == 500, f"期望 500, 实际 {r.status_code}: {r.text}"
    assert "boom" in r.json().get("detail", "")


def test_g7_graph_engine_exception_returns_500(raising_client):
    """G-7-2: /graph 引擎异常 → 500。"""
    r = raising_client.post("/api/semantic-retrieval/graph", json={"query": "x"})
    assert r.status_code == 500
    assert "graph boom" in r.json().get("detail", "")


def test_g7_nl_engine_exception_returns_500(raising_client):
    """G-7-3: /nl 引擎异常 → 500。"""
    r = raising_client.post("/api/semantic-retrieval/nl", json={"query": "x"})
    assert r.status_code == 500
    assert "nl boom" in r.json().get("detail", "")


def test_g7_metric_engine_exception_returns_500(raising_client):
    """G-7-4: /metric 引擎异常 → 500。"""
    r = raising_client.post(
        "/api/semantic-retrieval/metric", json={"metric": "count"}
    )
    assert r.status_code == 500
    assert "metric boom" in r.json().get("detail", "")


def test_g7_chain_engine_exception_returns_500(raising_client):
    """G-7-5: /chain 引擎异常 → 500。"""
    r = raising_client.post(
        "/api/semantic-retrieval/chain",
        json={"query": "x", "rules": [], "max_depth": 5},
    )
    assert r.status_code == 500
    assert "chain boom" in r.json().get("detail", "")


def test_g7_mdl_engine_exception_returns_500(raising_client):
    """G-7-6: /mdl 引擎异常 → 500。"""
    r = raising_client.post(
        "/api/semantic-retrieval/mdl",
        json={"query": "template: t\nentity: e"},
    )
    assert r.status_code == 500
    assert "mdl boom" in r.json().get("detail", "")


def test_g7_hybrid_engine_exception_returns_500(raising_client):
    """G-7-7: /hybrid 引擎异常 → 500。"""
    r = raising_client.post(
        "/api/semantic-retrieval/hybrid",
        json={"components": [{"type": "graph", "params": {"query": "x"}}]},
    )
    assert r.status_code == 500
    assert "hybrid boom" in r.json().get("detail", "")


# ── G-7-8: ValueError → 400（不混入 500） ──────────────────────────────────

def test_g7_value_error_returns_400_not_500(monkeypatch):
    """G-7-8: 引擎抛 ValueError（如非法 granularity）→ 400 而非 500。"""
    from odap.biz.core.ontology.semantic_retrieval.api import routes as sr_routes
    from odap.infra.security.jwt_auth import get_current_user

    app = FastAPI()
    app.include_router(sr_routes.router)
    app.dependency_overrides[get_current_user] = lambda: {"sub": "u1", "ws_id": "ws-x"}

    class ValueErrorService:
        async def metric_search(self, ws, metric, **kw):
            raise ValueError("granularity must be day|week|month")

    monkeypatch.setattr(sr_routes, "_service", ValueErrorService())
    c = TestClient(app, raise_server_exceptions=False)
    r = c.post("/api/semantic-retrieval/metric", json={"metric": "trend", "granularity": "hour"})
    assert r.status_code == 400, f"期望 400 (ValueError), 实际 {r.status_code}"
    assert "granularity" in r.json().get("detail", "")


# ── G-7-9: 异常后服务器仍可服务下一请求（无状态泄漏） ──────────────────────

def test_g7_server_recovers_after_exception(raising_client):
    """G-7-9: 一次 500 后服务器仍能处理下一请求（无状态泄漏/线程崩溃）。"""
    # 第一次请求触发 500
    r1 = raising_client.post("/api/semantic-retrieval/nl", json={"query": "x"})
    assert r1.status_code == 500
    # 第二次请求仍应正常进入异常分支（证明服务器没崩溃）
    r2 = raising_client.post("/api/semantic-retrieval/nl", json={"query": "y"})
    assert r2.status_code == 500, "第二次请求未返回 500 — 服务器可能在首次异常后崩溃"
    # 响应体仍可序列化
    assert isinstance(r2.json(), dict)
