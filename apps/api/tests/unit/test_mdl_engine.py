"""T015 [P] US3: MDL/DSL 推理（TDD RED → GREEN）。

测试目标（spec FR-004 / contracts api-contracts.md L176-188 / Q6 决策）:
  Q6 决策：禁止新发明 DSL。MDL 仅解析 query 字符串中的 HE YAML 模板引用
           + 实体 + 参数，复用 HE 模板体系，不发明新语法。
  契约：query = "template: {name}\nentity: {entity}\nparams: {json_or_kv}"
  响应：同 /chain 结构 — mode="mdl", reasoning{template, entity, params, status}

T015-1: 合法 query 解析 — template/entity/params 三段正确提取
T015-2: 模板引用不存在 — 优雅降级 status=degraded（不抛异常）
T015-3: 缺 template 关键字 — ValueError（契约违反）
T015-4: params 多格式 — JSON 串 / key=value kv 串 均可解析为 dict
T015-5: 输出结构完整 — mode/reasoning/total 字段齐全
"""

from __future__ import annotations

import pytest


# ── T015-1: 合法 query 解析 ───────────────────────────────────────────────

@pytest.mark.asyncio
async def test_valid_query_parses_template_entity_params():
    """T015-1: 标准 query 三段解析正确。"""
    from odap.biz.core.ontology.semantic_retrieval.impl.mdl_engine import MdlEngine

    engine = MdlEngine()
    query = (
        "template: risk_propagation\n"
        "entity: 装备A\n"
        'params: {"threshold": 0.6, "depth": 3}'
    )
    result = await engine.reason("ws-test", query=query)

    assert result["mode"] == "mdl"
    reasoning = result["reasoning"]
    assert reasoning["template"] == "risk_propagation"
    assert reasoning["entity"] == "装备A"
    params = reasoning["params"]
    assert isinstance(params, dict)
    assert params.get("threshold") == 0.6
    assert params.get("depth") == 3
    # 模板存在性不强求（Phase 1 不调用 HE），但状态字段必有
    assert "status" in reasoning
    assert reasoning["status"] in ("ok", "degraded")


# ── T015-2: 模板引用不存在 → 优雅降级 ─────────────────────────────────────

@pytest.mark.asyncio
async def test_template_not_found_degrades_gracefully():
    """T015-2: 模板名不在 HE preset 中 → status=degraded + warning。"""
    from odap.biz.core.ontology.semantic_retrieval.impl.mdl_engine import MdlEngine

    engine = MdlEngine()
    query = (
        "template: non_existent_template_xyz\n"
        "entity: 装备A\n"
        "params: {}"
    )
    result = await engine.reason("ws-test", query=query)

    reasoning = result["reasoning"]
    # 优雅降级：不抛异常，标记 status=degraded
    assert reasoning["status"] == "degraded"
    # warnings 含降级提示
    assert any("模板" in w or "template" in w.lower() for w in result["warnings"]), (
        f"模板不存在时未生成警告: {result['warnings']}"
    )


# ── T015-3: 缺 template 关键字 → ValueError ──────────────────────────────

@pytest.mark.asyncio
async def test_missing_template_keyword_raises_value_error():
    """T015-3: query 不含 template: 行 → 契约违反 → ValueError。"""
    from odap.biz.core.ontology.semantic_retrieval.impl.mdl_engine import MdlEngine

    engine = MdlEngine()
    with pytest.raises(ValueError) as exc_info:
        await engine.reason("ws-test", query="entity: 装备A\nparams: {}")
    msg = str(exc_info.value).lower()
    assert "template" in msg


# ── T015-4: params 多格式解析 ─────────────────────────────────────────────

@pytest.mark.asyncio
async def test_params_kv_format_parsed_as_dict():
    """T015-4a: params 使用 key=value 格式 → 解析为 dict。"""
    from odap.biz.core.ontology.semantic_retrieval.impl.mdl_engine import MdlEngine

    engine = MdlEngine()
    query = (
        "template: risk_propagation\n"
        "entity: 装备A\n"
        "params: threshold=0.6, depth=3"
    )
    result = await engine.reason("ws-test", query=query)

    params = result["reasoning"]["params"]
    assert isinstance(params, dict)
    assert params.get("threshold") == 0.6 or params.get("threshold") == "0.6"
    assert params.get("depth") == 3 or params.get("depth") == "3"


@pytest.mark.asyncio
async def test_params_missing_returns_empty_dict():
    """T015-4b: query 不含 params 行 → params={} 默认值。"""
    from odap.biz.core.ontology.semantic_retrieval.impl.mdl_engine import MdlEngine

    engine = MdlEngine()
    query = "template: risk_propagation\nentity: 装备A"
    result = await engine.reason("ws-test", query=query)

    params = result["reasoning"]["params"]
    assert params == {}


# ── T015-5: 输出结构完整 ──────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_output_structure_complete():
    """T015-5: 完整响应字段 mode/reasoning/total/warnings 齐全。"""
    from odap.biz.core.ontology.semantic_retrieval.impl.mdl_engine import MdlEngine

    engine = MdlEngine()
    query = (
        "template: risk_propagation\n"
        "entity: 装备A\n"
        'params: {"threshold": 0.6}'
    )
    result = await engine.reason("ws-test", query=query)

    # 顶层字段
    assert set(["mode", "reasoning", "total", "warnings"]).issubset(result.keys())
    assert result["mode"] == "mdl"
    assert isinstance(result["total"], int)
    assert isinstance(result["warnings"], list)
    # reasoning 必填字段
    reasoning = result["reasoning"]
    assert {"template", "entity", "params", "status", "chain_id"}.issubset(
        reasoning.keys()
    ), f"reasoning 字段缺失: {reasoning.keys()}"
    assert isinstance(reasoning["chain_id"], str) and reasoning["chain_id"]


# ── UnifiedRouter 适配器：.search(ws, query, limit) ────────────────────────

@pytest.mark.asyncio
async def test_search_adapter_routes_to_reason():
    """T015-6: .search() 是 UnifiedRouter 适配器，转发到 .reason()。"""
    from odap.biz.core.ontology.semantic_retrieval.impl.mdl_engine import MdlEngine

    engine = MdlEngine()
    query = "template: risk_propagation\nentity: 装备A"
    result = await engine.search("ws-test", query, limit=20)

    assert result["mode"] == "mdl"
    assert result["reasoning"]["template"] == "risk_propagation"
