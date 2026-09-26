"""QueryPipeline 共享单例与显式失败语义测试。

覆盖此前零测试的两处静默降级：
  1. nl_routes._get_pipeline 用 `except Exception: pass` 把 GraphManager 构造失败吞成
     None，却仍把降级实例写入模块级单例 —— 一次 Neo4j 抖动即把整个进程生命周期内的 QA
     永久钉死在"无图谱"状态，向量/图谱两个支柱静默失效，接口照常返回 200。
  2. QueryPipeline.__init__ 同样吞掉 create_llm_client 失败，使 UnderstandingStage /
     GenerationStage / QueryRewriter / CypherGenerator 四处同时拿到 None。

另含 tools/query/nl_query_skills 的回归：它原先每次 `QueryPipeline()` 不传 graph_manager，
Agent 侧 NL 技能的两个支柱恒为空却照样报 status=success。
"""

import pytest
from unittest.mock import AsyncMock, MagicMock, patch

import odap.biz.data.qa.pipeline.query_pipeline as qp_mod
from odap.biz.data.qa.pipeline.query_pipeline import QueryPipeline, get_query_pipeline

_GRAPH_MANAGER_PATH = "odap.infra.graph.graph_service.GraphManager"
_LLM_FACTORY_PATH = "odap.biz.data.qa.pipeline.llm_client.create_llm_client"


@pytest.fixture(autouse=True)
def _isolate(tmp_path, monkeypatch):
    """每例前后清空共享单例，并把 DATA_DIR 指到 tmp_path。

    QueryPipeline 构造会建 QueryAuditStorage（SQLite），不隔离就会写到 pytest 的
    CWD（仓库根）下，违反规则 13。
    """
    monkeypatch.setenv("DATA_DIR", str(tmp_path))
    qp_mod._pipeline_singleton = None
    yield
    qp_mod._pipeline_singleton = None


# ---------------------------------------------------------------------------
# TestGetQueryPipeline — 共享单例的接线与失败语义
# ---------------------------------------------------------------------------

class TestGetQueryPipeline:
    def test_wires_real_graph_manager(self):
        """单例必须把 GraphManager 接进管线，而不是留 None。"""
        gm = MagicMock(name="GraphManager")

        with patch(_GRAPH_MANAGER_PATH, return_value=gm):
            pipeline = get_query_pipeline()

        assert pipeline._graph_manager is gm

    def test_wires_llm_client(self):
        with patch(_GRAPH_MANAGER_PATH, return_value=MagicMock()):
            pipeline = get_query_pipeline()

        assert pipeline._llm_client is not None

    def test_returns_same_instance_on_repeat_calls(self):
        with patch(_GRAPH_MANAGER_PATH, return_value=MagicMock()) as gm_cls:
            first = get_query_pipeline()
            second = get_query_pipeline()

        assert first is second
        assert gm_cls.call_count == 1  # 不重复构造昂贵依赖

    def test_construction_failure_raises(self):
        """规则 14：依赖构造失败必须显式抛出，不得降级成 graph_manager=None。"""
        with patch(_GRAPH_MANAGER_PATH, side_effect=RuntimeError("Neo4j 不可达")):
            with pytest.raises(RuntimeError, match="Neo4j 不可达"):
                get_query_pipeline()

    def test_failure_is_not_cached_so_transient_fault_self_heals(self):
        """核心回归：瞬时故障不得被冻结成进程级永久降级。"""
        gm = MagicMock(name="GraphManager")

        with patch(_GRAPH_MANAGER_PATH, side_effect=[RuntimeError("Neo4j 重启中"), gm]):
            with pytest.raises(RuntimeError, match="Neo4j 重启中"):
                get_query_pipeline()

            assert qp_mod._pipeline_singleton is None  # 失败未落缓存

            recovered = get_query_pipeline()

        assert recovered._graph_manager is gm


# ---------------------------------------------------------------------------
# TestQueryPipelineExplicitFailure — 构造函数不再吞 LLM 工厂失败
# ---------------------------------------------------------------------------

class TestQueryPipelineExplicitFailure:
    def test_llm_factory_failure_propagates(self):
        with patch(_LLM_FACTORY_PATH, side_effect=ImportError("llm_client 模块缺失")):
            with pytest.raises(ImportError, match="llm_client 模块缺失"):
                QueryPipeline()

    def test_explicit_none_llm_client_still_autowires(self):
        """显式传 None 等同不传，仍自动接线（保持既有调用方语义，如 test_domain_resolution_chain）。"""
        pipeline = QueryPipeline(llm_client=None, graph_manager=None)

        assert pipeline._llm_client is not None


# ---------------------------------------------------------------------------
# TestRouteTranslation — 抛错必须被路由层翻译成 503，而不是 200 + 空结果
# ---------------------------------------------------------------------------

class TestRouteTranslation:
    @pytest.mark.asyncio
    async def test_search_returns_503_when_pipeline_unavailable(self):
        from fastapi import HTTPException
        from odap.biz.data.qa.api.nl_routes import NLSearchRequest, nl_search

        # nl_routes 在模块级 import 了该名字，必须 patch 路由模块自己的绑定
        with patch(
            "odap.biz.data.qa.api.nl_routes.get_query_pipeline",
            side_effect=RuntimeError("Neo4j 不可达"),
        ):
            with pytest.raises(HTTPException) as exc_info:
                await nl_search(NLSearchRequest(query="荆州兵力"), user={"sub": "u1"})

        assert exc_info.value.status_code == 503
        assert "Neo4j 不可达" in exc_info.value.detail

    @pytest.mark.asyncio
    async def test_query_returns_503_when_pipeline_unavailable(self):
        from fastapi import HTTPException
        from odap.biz.data.qa.api.nl_routes import NLSearchRequest, nl_query

        with patch(
            "odap.biz.data.qa.api.nl_routes.get_query_pipeline",
            side_effect=RuntimeError("Neo4j 不可达"),
        ):
            with pytest.raises(HTTPException) as exc_info:
                await nl_query(NLSearchRequest(query="荆州兵力"), user={"sub": "u1"})

        assert exc_info.value.status_code == 503


# ---------------------------------------------------------------------------
# TestSkillHandlersUseSharedPipeline — Agent 侧技能不再自建无图谱管线
# ---------------------------------------------------------------------------

class TestSkillHandlersUseSharedPipeline:
    def test_nl_search_handler_uses_shared_pipeline(self):
        from odap.tools.query.nl_query_skills import _nl_search_handler

        fake_pipeline = MagicMock()
        fake_result_set = MagicMock()
        fake_result_set.results = []
        fake_result_set.pillar_scores = {}
        fake_pipeline.search = AsyncMock(return_value=fake_result_set)

        with patch(
            "odap.biz.data.qa.pipeline.query_pipeline.get_query_pipeline",
            return_value=fake_pipeline,
        ):
            result = _nl_search_handler(query="荆州兵力")

        assert result["status"] == "success"
        fake_pipeline.search.assert_awaited_once()

    def test_nl_search_handler_reports_error_not_fake_success(self):
        """管线构造失败时技能必须返回 status=error，而不是空结果的 success。"""
        from odap.tools.query.nl_query_skills import _nl_search_handler

        with patch(
            "odap.biz.data.qa.pipeline.query_pipeline.get_query_pipeline",
            side_effect=RuntimeError("Neo4j 不可达"),
        ):
            result = _nl_search_handler(query="荆州兵力")

        assert result["status"] == "error"
        assert "Neo4j 不可达" in result["message"]
