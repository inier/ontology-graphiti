"""T019 [P] US5: MCP 工具集成测试（TDD RED → GREEN）。

测试目标（tasks.md T019 + spec FR-009/010 + contracts L226-236）:
  FR-009: 7 个端点能力注册为 MCP 工具
  FR-010: MCP 调用结果与直接 REST API 调用完全一致

3 个 MCP 工具（contracts L232-234）:
  - ontology_query   → POST /query   (统一检索)
  - ontology_reason  → POST /chain   (链式推理)
  - ontology_metric  → POST /metric  (指标查询)

TDD 策略：
  · 不启动 HTTP 服务器（避免 Neo4j/JWT 重依赖）
  · 直接调用 MCP 工具函数 vs RetrievalService 方法
  · 断言两者返回结构等价（FR-010 一致性）
"""

from __future__ import annotations

import pytest


# ── T019-1: 3 个 MCP 工具均已注册 ────────────────────────────────────────

def test_three_mcp_tools_registered():
    """T019-1: register_all() 后 ontology_query/reason/metric 3 工具可发现。"""
    from odap.biz.core.ontology.mcp.semantic_retrieval_tools import register_all

    class FakeRegistry:
        def __init__(self):
            self.tools = {}

        def register_function(self, name, description, func, category="function"):
            self.tools[name] = {
                "description": description,
                "func": func,
                "category": category,
            }
            return True

    reg = FakeRegistry()
    register_all(registry=reg)

    assert "ontology_query" in reg.tools, "ontology_query 未注册"
    assert "ontology_reason" in reg.tools, "ontology_reason 未注册"
    assert "ontology_metric" in reg.tools, "ontology_metric 未注册"
    # 描述非空
    for name in ("ontology_query", "ontology_reason", "ontology_metric"):
        assert reg.tools[name]["description"], f"{name} 描述为空"


# ── T019-2: ontology_query 调用结果与 RetrievalService 一致 (FR-010) ──────

@pytest.mark.asyncio
async def test_ontology_query_result_matches_service():
    """T019-2: MCP ontology_query 调用 → 结果与 RetrievalService.search 一致。"""
    from odap.biz.core.ontology.mcp.semantic_retrieval_tools import (
        create_ontology_query_handler,
    )
    from odap.biz.core.ontology.semantic_retrieval.models.schemas import SearchRequest

    # 用 FakeService 隔离真实引擎
    class FakeService:
        async def search(self, workspace_id, request):
            return {
                "query": request.query,
                "mode": request.mode,
                "total": 1,
                "rows": [{"id": "fake1"}],
            }

    svc = FakeService()
    handler = create_ontology_query_handler(service=svc)

    # MCP 工具入参（dict 形式，FR-010 契约）
    args = {"query": "测试查询", "mode": "auto", "workspace_id": "ws-test"}
    result = await handler(args)

    assert result["total"] == 1
    assert result["rows"] == [{"id": "fake1"}]
    assert result["mode"] == "auto"


# ── T019-3: ontology_reason 调用结果与 chain_search 一致 (FR-010) ──────────

@pytest.mark.asyncio
async def test_ontology_reason_result_matches_service():
    """T019-3: MCP ontology_reason 调用 → 结果与 RetrievalService.chain_search 一致。"""
    from odap.biz.core.ontology.mcp.semantic_retrieval_tools import (
        create_ontology_reason_handler,
    )

    class FakeService:
        async def chain_search(self, workspace_id, *, query, rules, max_depth):
            return {
                "mode": "chain",
                "reasoning": {
                    "chain_id": "c1",
                    "steps": [],
                    "conclusion": query,
                    "cycle_detected": False,
                    "conflicts": [],
                },
                "warnings": [],
                "total": 0,
            }

    svc = FakeService()
    handler = create_ontology_reason_handler(service=svc)
    args = {
        "query": "风险传导",
        "rules": ["R1", "R2"],
        "max_depth": 5,
        "workspace_id": "ws-test",
    }
    result = await handler(args)

    assert result["mode"] == "chain"
    assert result["reasoning"]["chain_id"] == "c1"
    assert result["reasoning"]["conclusion"] == "风险传导"


# ── T019-4: ontology_metric 调用结果与 metric_search 一致 (FR-010) ─────────

@pytest.mark.asyncio
async def test_ontology_metric_result_matches_service():
    """T019-4: MCP ontology_metric 调用 → 结果与 RetrievalService.metric_search 一致。"""
    from odap.biz.core.ontology.mcp.semantic_retrieval_tools import (
        create_ontology_metric_handler,
    )

    class FakeService:
        async def metric_search(
            self, workspace_id, metric, *,
            object_type=None, granularity=None, time_window=None, limit=20,
        ):
            return {
                "mode": "metric",
                "metrics": [{"value": 42}],
                "rows": [{"value": 42}],
                "total": 1,
                "explain": {"source": "metric", "status": "ok"},
            }

    svc = FakeService()
    handler = create_ontology_metric_handler(service=svc)
    args = {
        "metric": "count",
        "object_type": "装备",
        "granularity": None,
        "workspace_id": "ws-test",
    }
    result = await handler(args)

    assert result["mode"] == "metric"
    assert result["total"] == 1
    assert result["rows"] == [{"value": 42}]


# ── T019-5: 工具描述包含输入 schema 提示（contracts L232-234 字段） ────────

def test_tool_descriptions_document_input_fields():
    """T019-5: 工具 description 文档化 input_schema 关键字段（contracts L232-234）。"""
    from odap.biz.core.ontology.mcp.semantic_retrieval_tools import register_all

    class FakeRegistry:
        def __init__(self):
            self.tools = {}

        def register_function(self, name, description, func, category="function"):
            self.tools[name] = {"description": description}
            return True

    reg = FakeRegistry()
    register_all(registry=reg)

    # ontology_query: query + (filters)
    desc_q = reg.tools["ontology_query"]["description"]
    assert "query" in desc_q.lower(), f"ontology_query 缺 query 字段: {desc_q}"

    # ontology_reason: query + rules + max_depth
    desc_r = reg.tools["ontology_reason"]["description"]
    assert "rule" in desc_r.lower() or "max_depth" in desc_r.lower(), (
        f"ontology_reason 缺 rules/max_depth: {desc_r}"
    )

    # ontology_metric: metric_type + target + granularity
    desc_m = reg.tools["ontology_metric"]["description"]
    assert "metric" in desc_m.lower(), f"ontology_metric 缺 metric 字段: {desc_m}"
