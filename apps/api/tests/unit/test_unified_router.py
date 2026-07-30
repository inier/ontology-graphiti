"""TDD tests for UnifiedRouter (spec 008 / US1 / FR-001 统一检索自动路由).

RED 阶段：先于 impl/unified_router.py 编写，运行应失败。
Constitution IV：路由器用 dict 策略表分发，非抽象工厂。
"""

import pytest
from unittest.mock import AsyncMock, MagicMock

pytestmark = pytest.mark.asyncio


def _mock_engine(rows=None, source="mock"):
    """构造 mock 引擎（含 .search 异步方法）。"""
    eng = MagicMock()
    eng.search = AsyncMock(
        return_value={
            "rows": rows if rows is not None else [{"id": "x1"}],
            "total": len(rows) if rows is not None else 1,
            "explain": {"source": source},
        }
    )
    return eng


async def test_auto_routes_to_nl_default():
    """mode=auto 时路由到默认 nl 引擎。"""
    from odap.biz.core.ontology.semantic_retrieval.impl.unified_router import UnifiedRouter

    nl = _mock_engine(source="nl")
    router = UnifiedRouter(engines={"nl": nl})

    result = await router.route("ws-test", "装备", mode="auto", limit=10)

    assert result["mode"] == "nl"
    nl.search.assert_awaited_once()


async def test_explicit_graph_mode():
    """mode=graph 时路由到 graph 引擎。"""
    from odap.biz.core.ontology.semantic_retrieval.impl.unified_router import UnifiedRouter

    graph = _mock_engine(source="graph")
    router = UnifiedRouter(engines={"graph": graph})

    result = await router.route("ws-test", "装备", mode="graph", limit=10)

    assert result["mode"] == "graph"
    graph.search.assert_awaited_once()


async def test_explicit_nl_mode():
    """mode=nl 时路由到 nl 引擎。"""
    from odap.biz.core.ontology.semantic_retrieval.impl.unified_router import UnifiedRouter

    nl = _mock_engine(source="nl")
    router = UnifiedRouter(engines={"nl": nl})

    await router.route("ws-test", "装备", mode="nl", limit=10)

    nl.search.assert_awaited_once()


async def test_unsupported_mode_raises():
    """未注册的 mode（如 chain，MVP 未实现）抛 ValueError。"""
    from odap.biz.core.ontology.semantic_retrieval.impl.unified_router import UnifiedRouter

    nl = _mock_engine(source="nl")
    router = UnifiedRouter(engines={"nl": nl})

    with pytest.raises(ValueError, match="unsupported"):
        await router.route("ws-test", "装备", mode="chain", limit=10)


async def test_auto_no_engines_raises():
    """engines 为空时 auto 路由抛 ValueError。"""
    from odap.biz.core.ontology.semantic_retrieval.impl.unified_router import UnifiedRouter

    router = UnifiedRouter(engines={})
    with pytest.raises(ValueError, match="unsupported"):
        await router.route("ws-test", "装备", mode="auto", limit=10)


async def test_route_preserves_engine_result_fields():
    """路由结果保留引擎返回的 rows/total/explain，并附 mode。"""
    from odap.biz.core.ontology.semantic_retrieval.impl.unified_router import UnifiedRouter

    nl = _mock_engine(rows=[{"id": "a"}, {"id": "b"}], source="nl")
    router = UnifiedRouter(engines={"nl": nl})

    result = await router.route("ws-test", "q", mode="nl", limit=5)

    assert result["total"] == 2
    assert len(result["rows"]) == 2
    assert result["explain"]["source"] == "nl"
    assert result["mode"] == "nl"
