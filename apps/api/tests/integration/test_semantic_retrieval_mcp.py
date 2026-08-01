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
        async def chain_search(self, workspace_id, *, query, rules, max_depth, persist_candidates=False):
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


# ══════════════════════════════════════════════════════════════════════
# Phase 3 T035: MCP 工具对真实 RetrievalService 的端到端调用验证 (FR-010)
# ══════════════════════════════════════════════════════════════════════


# ── T035-1: ontology_metric 对 real RetrievalService 调 count/density/trend ─

@pytest.mark.asyncio
async def test_mcp_ontology_metric_count_matches_service_directly():
    """T035-1: MCP metric count 结果与直接 RetrievalService.metric_search 完全一致 (FR-010)。"""
    from odap.biz.core.ontology.mcp.semantic_retrieval_tools import (
        create_ontology_metric_handler,
    )
    from odap.biz.core.ontology.semantic_retrieval.services.retrieval_service import (
        RetrievalService,
    )

    svc = RetrievalService()
    handler = create_ontology_metric_handler(service=svc)

    args = {"metric": "count", "object_type": None, "workspace_id": "ws-mcp"}
    via_handler = await handler(args)
    via_direct = await svc.metric_search("ws-mcp", "count")

    assert via_handler["mode"] == via_direct["mode"] == "metric"
    assert via_handler["total"] == via_direct["total"]
    # metrics 内容等价（元素逐项对比，允许模型内序列化差异）
    assert isinstance(via_handler["metrics"], list)
    handler_vals = [m.get("value") for m in via_handler["metrics"]]
    direct_vals = [m.get("value") for m in via_direct["metrics"]]
    assert handler_vals == direct_vals, "handler 与 direct metric_search 结果不一致 (FR-010)"


# ── T035-2: ontology_reason 对 real RetrievalService 结构契约对齐 ─────

@pytest.mark.asyncio
async def test_mcp_ontology_reason_chain_id_conclusion_fields_exist():
    """T035-2: MCP ontology_reason 返回结构含 chain_id + conclusion + status (FR-010)。"""
    from odap.biz.core.ontology.mcp.semantic_retrieval_tools import (
        create_ontology_reason_handler,
    )
    from odap.biz.core.ontology.semantic_retrieval.services.retrieval_service import (
        RetrievalService,
    )

    svc = RetrievalService()
    handler = create_ontology_reason_handler(service=svc)
    args = {
        "query": "测试起点 -> 规则A -> 规则B",
        "rules": ["R-A", "R-B"],
        "max_depth": 3,
        "workspace_id": "ws-mcp",
    }
    via_handler = await handler(args)
    via_direct = await svc.chain_search(
        "ws-mcp", query=args["query"], rules=args["rules"], max_depth=args["max_depth"],
    )

    assert via_handler["mode"] == via_direct["mode"] == "chain"
    reasoning = via_handler["reasoning"]
    # FR-010 结构契约：chain_id / conclusion / cycle_detected / conflicts 必存
    for field in ("chain_id", "conclusion", "cycle_detected", "conflicts", "status", "confidence"):
        assert field in reasoning, (
            f"ontology_reason 缺字段 {field}（FR-010 结构对齐）"
        )
    assert via_handler["warnings"] is not None
    assert isinstance(via_handler.get("warnings"), list)


# ── T035-3: MCP register_all 返回 handlers 可直接调用 7 工具 ────────────

def test_mcp_register_all_returns_callable_handlers():
    """T035-3: register_all 返回 {name: async handler}，7 工具均 callable + 正确 shape。

    Phase 5 扩编后工具数 3→7（新增 graph/nl/mdl/hybrid）；3 核心 + 4 扩展均需满足契约。
    """
    import inspect

    from odap.biz.core.ontology.mcp.semantic_retrieval_tools import register_all

    class CapturingRegistry:
        def __init__(self):
            self.items = []

        def register_function(self, name, description, func, category="function"):
            self.items.append((name, description, func, category))
            return True

    reg = CapturingRegistry()
    handlers = register_all(registry=reg)

    # 返回值 7 个（Phase 5：3 核心 + 4 扩展）
    expected = {
        "ontology_query", "ontology_reason", "ontology_metric",  # 核心 3
        "ontology_graph", "ontology_nl", "ontology_mdl", "ontology_hybrid",  # 扩展 4
    }
    assert set(handlers.keys()) == expected, f"工具集不符: {set(handlers.keys())}"
    for name, fn in handlers.items():
        assert callable(fn), f"{name} handler 不可调用"
        # async callable
        assert inspect.iscoroutinefunction(fn), f"{name} handler 非 async"
    # 注册项 7 个，均带 category=semantic_retrieval
    assert len(reg.items) == 7
    cats = {item[3] for item in reg.items}
    assert "semantic_retrieval" in cats, f"category 缺失 semantic_retrieval: {cats}"


# ── T035-4: ontology_query 缺 query 参数 → 显式错误（不崩溃） ─────────

@pytest.mark.asyncio
async def test_mcp_query_missing_query_arg_raises_key_error_or_value_error():
    """T035-4: MCP ontology_query 缺 query → 显式异常（API 调用方便于 400）。"""
    from odap.biz.core.ontology.mcp.semantic_retrieval_tools import (
        create_ontology_query_handler,
    )
    from odap.biz.core.ontology.semantic_retrieval.services.retrieval_service import (
        RetrievalService,
    )

    handler = create_ontology_query_handler(service=RetrievalService())
    with pytest.raises((KeyError, ValueError)):
        # 故意不传 "query" 字段，触发契约错误
        await handler({"mode": "auto", "workspace_id": "ws-x"})  # type: ignore[typeddict-item]


# ── T035-5: register_all(category=semantic_retrieval) 与 contracts L232-234 对齐

def test_mcp_descriptions_match_contract_field_names():
    """T035-5: 3 个 MCP 工具 description 字段名与 contracts/api-contracts.md L232-234 对齐。"""
    from odap.biz.core.ontology.mcp.semantic_retrieval_tools import register_all

    class CaptureReg:
        def __init__(self): self.items = {}
        def register_function(self, name, description, func, category="function"):
            self.items[name] = description
            return True

    reg = CaptureReg()
    register_all(registry=reg)
    q = reg.items["ontology_query"].lower()
    r = reg.items["ontology_reason"].lower()
    m = reg.items["ontology_metric"].lower()
    # contracts L232: query + workspace_id + mode + limit
    for field in ("query", "workspace_id", "mode", "limit"):
        assert field in q, f"ontology_query 描述缺 {field}"
    # contracts L233: query + rules + max_depth + workspace_id
    for field in ("query", "rule", "max_depth", "workspace_id"):
        if field == "rule":
            assert field in r or "rules" in r, f"ontology_reason 描述缺 {field}/rules"
        else:
            assert field in r, f"ontology_reason 描述缺 {field}"
    # contracts L234: metric + object_type + granularity + workspace_id
    for field in ("metric", "object_type", "granularity", "workspace_id"):
        assert field in m, f"ontology_metric 描述缺 {field}"


# ══════════════════════════════════════════════════════════════════════
# Phase 5 T040: MCP 工具组扩编 3→7 (FR-009 全端点覆盖)
# ══════════════════════════════════════════════════════════════════════


# ── T040-1: 7 个 MCP 工具均已注册 ────────────────────────────────────────

def test_seven_mcp_tools_registered():
    """T040-1: register_all() 后 7 工具可发现（3 核心 + 4 扩展）。"""
    from odap.biz.core.ontology.mcp.semantic_retrieval_tools import register_all

    class FakeRegistry:
        def __init__(self):
            self.tools = {}
        def register_function(self, name, description, func, category="function"):
            self.tools[name] = {"description": description, "func": func}
            return True

    reg = FakeRegistry()
    register_all(registry=reg)

    expected = {
        "ontology_query", "ontology_reason", "ontology_metric",  # 核心 3
        "ontology_graph", "ontology_nl", "ontology_mdl", "ontology_hybrid",  # 扩展 4
    }
    actual = set(reg.tools.keys())
    missing = expected - actual
    assert not missing, f"未注册工具: {missing}（实际: {actual}）"


# ── T040-2: ontology_graph 调用结果与 RetrievalService.graph_search 一致 ─

@pytest.mark.asyncio
async def test_ontology_graph_result_matches_service():
    """T040-2: MCP ontology_graph → 结果与 RetrievalService.graph_search 一致 (FR-010)。"""
    from odap.biz.core.ontology.mcp.semantic_retrieval_tools import (
        create_ontology_graph_handler,
    )

    class FakeService:
        async def graph_search(self, workspace_id, query, limit=20):
            return {
                "mode": "graph",
                "total": 2,
                "rows": [{"id": "g1"}, {"id": "g2"}],
                "explain": {"source": "graph"},
            }

    svc = FakeService()
    handler = create_ontology_graph_handler(service=svc)
    args = {"query": "部署于", "limit": 50, "workspace_id": "ws-test"}
    result = await handler(args)

    assert result["mode"] == "graph"
    assert result["total"] == 2
    assert result["rows"] == [{"id": "g1"}, {"id": "g2"}]


# ── T040-3: ontology_nl 调用结果与 RetrievalService.nl_search 一致 ───────

@pytest.mark.asyncio
async def test_ontology_nl_result_matches_service():
    """T040-3: MCP ontology_nl → 结果与 RetrievalService.nl_search 一致 (FR-010)。"""
    from odap.biz.core.ontology.mcp.semantic_retrieval_tools import (
        create_ontology_nl_handler,
    )

    class FakeService:
        async def nl_search(self, workspace_id, query, limit=20):
            return {
                "mode": "nl",
                "total": 1,
                "rows": [{"id": "n1"}],
                "explain": {"source": "nl"},
            }

    svc = FakeService()
    handler = create_ontology_nl_handler(service=svc)
    args = {"query": "低 readiness 装备", "workspace_id": "ws-test"}
    result = await handler(args)

    assert result["mode"] == "nl"
    assert result["total"] == 1
    assert result["rows"] == [{"id": "n1"}]


# ── T040-4: ontology_mdl 调用结果与 RetrievalService.mdl_search 一致 ──────

@pytest.mark.asyncio
async def test_ontology_mdl_result_matches_service():
    """T040-4: MCP ontology_mdl → 结果与 RetrievalService.mdl_search 一致 (FR-010)。"""
    from odap.biz.core.ontology.mcp.semantic_retrieval_tools import (
        create_ontology_mdl_handler,
    )

    class FakeService:
        async def mdl_search(self, workspace_id, *, query, persist_candidates=False):
            return {
                "mode": "mdl",
                "reasoning": {
                    "chain_id": "mdl-test",
                    "template": "general/concept_graph",
                    "entity": "测试实体",
                    "status": "ok",
                    "conclusion": "测试结论",
                    "confidence": 0.8,
                    "cycle_detected": False,
                    "conflicts": [],
                },
                "warnings": [],
                "total": 1,
            }

    svc = FakeService()
    handler = create_ontology_mdl_handler(service=svc)
    args = {
        "query": "template: general/concept_graph\nentity: 测试实体\nparams: {}",
        "workspace_id": "ws-test",
    }
    result = await handler(args)

    assert result["mode"] == "mdl"
    assert result["reasoning"]["template"] == "general/concept_graph"
    assert result["reasoning"]["status"] == "ok"


# ── T040-5: ontology_hybrid 调用结果与 RetrievalService.hybrid_search 一致

@pytest.mark.asyncio
async def test_ontology_hybrid_result_matches_service():
    """T040-5: MCP ontology_hybrid → 结果与 RetrievalService.hybrid_search 一致 (FR-010)。"""
    from odap.biz.core.ontology.mcp.semantic_retrieval_tools import (
        create_ontology_hybrid_handler,
    )

    class FakeService:
        async def hybrid_search(self, workspace_id, components, *, merge="concat"):
            return {
                "mode": "hybrid",
                "request_id": "hybrid-test",
                "rows": [{"id": "h1"}],
                "total": 1,
                "components": [
                    {"type": "graph", "status": "ok", "rows": [{"id": "h1"}], "total": 1}
                ],
                "warnings": [],
            }

    svc = FakeService()
    handler = create_ontology_hybrid_handler(service=svc)
    args = {
        "components": [
            {"type": "graph", "params": {"query": "q"}, "on_failure": "skip"}
        ],
        "merge": "concat",
        "workspace_id": "ws-test",
    }
    result = await handler(args)

    assert result["mode"] == "hybrid"
    assert result["total"] == 1
    assert result["rows"] == [{"id": "h1"}]
    assert len(result["components"]) == 1


# ── T040-6: 7 工具 description 含必需字段名 ─────────────────────────────

def test_seven_tool_descriptions_document_fields():
    """T040-6: 7 个 MCP 工具 description 文档化 input_schema 关键字段。"""
    from odap.biz.core.ontology.mcp.semantic_retrieval_tools import register_all

    class FakeRegistry:
        def __init__(self):
            self.tools = {}
        def register_function(self, name, description, func, category="function"):
            self.tools[name] = {"description": description}
            return True

    reg = FakeRegistry()
    register_all(registry=reg)

    # ontology_graph: query + workspace_id + limit
    d = reg.tools["ontology_graph"]["description"].lower()
    for f in ("query", "workspace_id", "limit"):
        assert f in d, f"ontology_graph 描述缺 {f}"

    # ontology_nl: query + workspace_id
    d = reg.tools["ontology_nl"]["description"].lower()
    for f in ("query", "workspace_id"):
        assert f in d, f"ontology_nl 描述缺 {f}"

    # ontology_mdl: query + workspace_id
    d = reg.tools["ontology_mdl"]["description"].lower()
    for f in ("query", "workspace_id"):
        assert f in d, f"ontology_mdl 描述缺 {f}"

    # ontology_hybrid: components + workspace_id + merge
    d = reg.tools["ontology_hybrid"]["description"].lower()
    for f in ("component", "workspace_id", "merge"):
        assert f in d, f"ontology_hybrid 描述缺 {f}"


# ══════════════════════════════════════════════════════════════════════
# Phase 6 T042: 4 新 MCP 工具 real RetrievalService 端到端 (FR-010 补强)
#
# T035 已覆盖 metric/reason 2 工具的 real service 端到端；
# Phase 5 新增的 graph/nl/mdl/hybrid 4 工具仅有 FakeService 测试。
# 本节补齐：handler 调用 real RetrievalService → 结果与 direct 调用等价 (FR-010)。
# ══════════════════════════════════════════════════════════════════════


# ── T042-1: ontology_graph handler == direct graph_search (FR-010) ──────

@pytest.mark.asyncio
async def test_mcp_ontology_graph_real_service_equivalent_to_direct():
    """T042-1: ontology_graph handler 对 real RetrievalService → 与 direct graph_search 等价 (FR-010)。"""
    from odap.biz.core.ontology.mcp.semantic_retrieval_tools import (
        create_ontology_graph_handler,
    )
    from odap.biz.core.ontology.semantic_retrieval.services.retrieval_service import (
        RetrievalService,
    )

    svc = RetrievalService()
    handler = create_ontology_graph_handler(service=svc)
    args = {"query": "测试实体", "limit": 5, "workspace_id": "ws-mcp-real"}

    via_handler = await handler(args)
    via_direct = await svc.graph_search("ws-mcp-real", "测试实体", limit=5)

    # FR-010 核心断言：handler 与 direct 调用结果完全等价
    assert via_handler == via_direct, "ontology_graph handler 与 direct 结果不一致 (FR-010)"
    # 结构契约：rows/total/explain 必存
    for field in ("rows", "total", "explain"):
        assert field in via_handler, f"ontology_graph 缺字段 {field}"
    assert isinstance(via_handler["rows"], list)
    assert isinstance(via_handler["total"], int)


# ── T042-2: ontology_nl handler == direct nl_search (FR-010) ────────────

@pytest.mark.asyncio
async def test_mcp_ontology_nl_real_service_equivalent_to_direct():
    """T042-2: ontology_nl handler 对 real RetrievalService → 与 direct nl_search 等价 (FR-010)。"""
    from odap.biz.core.ontology.mcp.semantic_retrieval_tools import (
        create_ontology_nl_handler,
    )
    from odap.biz.core.ontology.semantic_retrieval.services.retrieval_service import (
        RetrievalService,
    )

    svc = RetrievalService()
    handler = create_ontology_nl_handler(service=svc)
    args = {"query": "低 readiness 装备", "limit": 5, "workspace_id": "ws-mcp-real"}

    via_handler = await handler(args)
    via_direct = await svc.nl_search("ws-mcp-real", "低 readiness 装备", limit=5)

    # FR-010 核心断言
    assert via_handler == via_direct, "ontology_nl handler 与 direct 结果不一致 (FR-010)"
    # 结构契约：rows/total/explain 必存
    for field in ("rows", "total", "explain"):
        assert field in via_handler, f"ontology_nl 缺字段 {field}"
    assert isinstance(via_handler["rows"], list)


# ── T042-3: ontology_mdl handler == direct mdl_search (FR-010) ──────────

@pytest.mark.asyncio
async def test_mcp_ontology_mdl_real_service_equivalent_to_direct():
    """T042-3: ontology_mdl handler 对 real RetrievalService → 与 direct mdl_search 等价 (FR-010)。"""
    from odap.biz.core.ontology.mcp.semantic_retrieval_tools import (
        create_ontology_mdl_handler,
    )
    from odap.biz.core.ontology.semantic_retrieval.services.retrieval_service import (
        RetrievalService,
    )

    svc = RetrievalService()
    handler = create_ontology_mdl_handler(service=svc)
    query = "template: general/concept_graph\nentity: 测试实体\nparams: {}"
    args = {"query": query, "workspace_id": "ws-mcp-real"}

    via_handler = await handler(args)
    via_direct = await svc.mdl_search("ws-mcp-real", query=query)

    # FR-010 核心断言（chain_id 是 UUID 每次不同，排除后比较）
    h_reasoning = {k: v for k, v in via_handler["reasoning"].items() if k != "chain_id"}
    d_reasoning = {k: v for k, v in via_direct["reasoning"].items() if k != "chain_id"}
    assert h_reasoning == d_reasoning, (
        "ontology_mdl handler 与 direct reasoning 不一致 (FR-010，排除 chain_id)"
    )
    # 非 reasoning 字段完全等价
    for field in ("mode", "warnings", "total"):
        assert via_handler[field] == via_direct[field], (
            f"ontology_mdl {field} 不一致 (FR-010)"
        )
    # 结构契约：mode/reasoning/warnings/total 必存
    for field in ("mode", "reasoning", "warnings", "total"):
        assert field in via_handler, f"ontology_mdl 缺字段 {field}"
    assert via_handler["mode"] == "mdl"
    # reasoning 子结构契约
    reasoning = via_handler["reasoning"]
    for field in ("chain_id", "template", "status", "conclusion"):
        assert field in reasoning, f"ontology_mdl reasoning 缺字段 {field}"


# ── T042-4: ontology_hybrid handler == direct hybrid_search (FR-010) ────

@pytest.mark.asyncio
async def test_mcp_ontology_hybrid_real_service_equivalent_to_direct():
    """T042-4: ontology_hybrid handler 对 real RetrievalService → 与 direct hybrid_search 等价 (FR-010)。"""
    from odap.biz.core.ontology.mcp.semantic_retrieval_tools import (
        create_ontology_hybrid_handler,
    )
    from odap.biz.core.ontology.semantic_retrieval.services.retrieval_service import (
        RetrievalService,
    )

    svc = RetrievalService()
    handler = create_ontology_hybrid_handler(service=svc)
    components = [
        {"type": "graph", "params": {"query": "测试"}, "on_failure": "skip"},
        {"type": "metric", "params": {"metric": "count"}, "on_failure": "degrade"},
    ]
    args = {
        "components": components,
        "merge": "concat",
        "workspace_id": "ws-mcp-real",
    }

    via_handler = await handler(args)
    via_direct = await svc.hybrid_search(
        "ws-mcp-real", components, merge="concat"
    )

    # FR-010 核心断言（request_id 是 UUID 每次不同，排除后比较）
    handler_no_rid = {k: v for k, v in via_handler.items() if k != "request_id"}
    direct_no_rid = {k: v for k, v in via_direct.items() if k != "request_id"}
    assert handler_no_rid == direct_no_rid, (
        "ontology_hybrid handler 与 direct 结果不一致 (FR-010，排除 request_id)"
    )
    # 结构契约：mode/request_id/rows/total/components/warnings 必存
    for field in ("mode", "request_id", "rows", "total", "components", "warnings"):
        assert field in via_handler, f"ontology_hybrid 缺字段 {field}"
    assert via_handler["mode"] == "hybrid"
    assert via_handler["request_id"].startswith("hybrid-")
    assert isinstance(via_handler["components"], list)
    assert len(via_handler["components"]) == 2  # 2 个组件
