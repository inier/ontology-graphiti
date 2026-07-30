"""TDD tests for NLEngine (spec 008 / US1 / FR-016 USL 术语消歧).

RED 阶段：本文件先于 impl/nl_engine.py 编写，运行时应失败（模块不存在）。
GREEN 阶段：实现 NLEngine 后全部通过。

 Constitution III：测试独立可运行，外部依赖（QueryService / USL）通过 mock 隔离。
"""

import pytest
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock

pytestmark = pytest.mark.asyncio


def _make_graph_engine(rows=None):
    """构造 mock graph_engine，search 返回固定 rows。"""
    ge = MagicMock()
    ge.search = AsyncMock(
        return_value={
            "rows": rows if rows is not None else [{"id": "e1", "name": "装备A"}],
            "total": len(rows) if rows is not None else 1,
            "explain": {"source": "graph"},
        }
    )
    return ge


def _make_usl_manager(term=None):
    """构造 mock usl_manager，list_terms 返回 [term] 或 []。"""
    um = MagicMock()
    if term is not None:
        um.list_terms = MagicMock(return_value=([term], 1))
    else:
        um.list_terms = MagicMock(return_value=([], 0))
    um.get_domain = MagicMock(
        return_value=SimpleNamespace(domain_id="dom-1", code="military", name="军事")
    )
    return um


# ---------------------------------------------------------------------------
# US1 验收：自然语言查询 + USL 自动消歧业务术语
# ---------------------------------------------------------------------------


async def test_nl_search_passthrough_without_usl():
    """无 USL 时降级为透传：仍返回 graph 结果，explain.usl 为 None。"""
    from odap.biz.core.ontology.semantic_retrieval.impl.nl_engine import NLEngine

    ge = _make_graph_engine()
    engine = NLEngine(graph_engine=ge, usl_manager=None)

    result = await engine.search("ws-test", "查一下装备A", limit=10)

    assert result["total"] == 1
    assert result["rows"][0]["id"] == "e1"
    assert result["explain"]["source"] == "nl"
    assert result["explain"]["usl"] is None
    ge.search.assert_awaited_once()


async def test_nl_search_with_usl_disambiguation():
    """USL 命中术语时，explain.usl 包含 domain 信息。"""
    from odap.biz.core.ontology.semantic_retrieval.impl.nl_engine import NLEngine

    term = SimpleNamespace(term_id="t1", term="装备", domain_id="dom-1")
    ge = _make_graph_engine()
    um = _make_usl_manager(term=term)

    engine = NLEngine(graph_engine=ge, usl_manager=um)
    result = await engine.search("ws-test", "装备", limit=10)

    assert result["explain"]["usl"] is not None
    assert result["explain"]["usl"]["domain_id"] == "dom-1"
    um.list_terms.assert_called_once()


async def test_nl_search_usl_error_degrades_gracefully():
    """USL 抛异常时不阻断检索，explain.usl.status='degraded'。"""
    from odap.biz.core.ontology.semantic_retrieval.impl.nl_engine import NLEngine

    ge = _make_graph_engine()
    um = MagicMock()
    um.list_terms = MagicMock(side_effect=RuntimeError("usl down"))

    engine = NLEngine(graph_engine=ge, usl_manager=um)
    result = await engine.search("ws-test", "装备", limit=10)

    assert result["total"] == 1  # 仍返回 graph 结果
    assert result["explain"]["usl"]["status"] == "degraded"


async def test_nl_search_excludes_invalid_rows():
    """FR-011：valid=False 的行不返回（graph_engine 已过滤，nl 透传）。"""
    from odap.biz.core.ontology.semantic_retrieval.impl.nl_engine import NLEngine

    rows = [
        {"id": "e1", "name": "有效", "valid": True},
        {"id": "c1", "name": "候选", "is_candidate": True},
    ]
    # graph_engine 已过滤候选行，仅返回有效行
    ge = _make_graph_engine(rows=[rows[0]])
    engine = NLEngine(graph_engine=ge, usl_manager=None)

    result = await engine.search("ws-test", "有效", limit=10)

    assert all(not r.get("is_candidate") for r in result["rows"])
    assert result["total"] == 1


async def test_nl_search_workspace_isolation():
    """FR-012：workspace_id 透传到 graph_engine。"""
    from odap.biz.core.ontology.semantic_retrieval.impl.nl_engine import NLEngine

    ge = _make_graph_engine()
    engine = NLEngine(graph_engine=ge, usl_manager=None)

    await engine.search("ws-isolated", "装备", limit=5)

    args, kwargs = ge.search.await_args
    # search(workspace_id, query, limit) 位置参数
    assert args[0] == "ws-isolated"
