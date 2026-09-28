"""GraphManager.delete_entity 软删除单元测试。

fallback 分支走真实函数体（规则 14 #6）；Neo4j 分支用 mock driver 断言 Cypher。
"""
import networkx as nx
import pytest
from unittest.mock import patch, MagicMock
from odap.infra.graph.graph_service import GraphManager


@pytest.fixture(autouse=True)
def _reset_gm_singleton():
    """GraphManager 是进程级单例；审计通道首次写入会构造 GraphManager() 触发 __init__。

    每个用例前后重置单例与 _initialized，避免 __init__ 复位 fallback_graph
    造成的跨用例状态泄漏（对齐 test_graph_service.py 的既有模式）。
    """
    GraphManager._instance = None
    GraphManager._initialized = False
    yield
    GraphManager._instance = None
    GraphManager._initialized = False


@pytest.fixture
def fb_gm():
    with patch.object(GraphManager, "_connect"):
        gm = GraphManager.__new__(GraphManager)
        gm._test_mode = True
        gm._connected = False
        gm._use_fallback = True
        gm._mode = "fallback"
        gm.graph = None
        gm.neo4j_driver = None
        gm.fallback_graph = nx.DiGraph()
        gm._query_cache = {}
        gm._query_cache_timestamps = {}
        gm._temporal_index = {}
        gm._temporal_index_built = False
        # 单例卫生：让审计通道构造 GraphManager() 时命中 __init__ 的 _initialized 早退，
        # 避免其复位 fallback_graph（否则首个用例会读到 None）
        GraphManager._instance = gm
        GraphManager._initialized = True
        yield gm


def _seed(gm):
    gm.fallback_graph.add_node("e1", entity_type="Agent", name="A")
    gm.fallback_graph.add_node("e2", entity_type="Agent", name="B")
    gm.fallback_graph.add_edge("e1", "e2", relationship="DEPENDS_ON")


class TestDeleteEntityFallback:
    def test_marks_invalid_at(self, fb_gm):
        _seed(fb_gm)
        result = fb_gm.delete_entity("e1")
        assert result["status"] == "success"
        assert result["entity_id"] == "e1"
        assert result["entities_invalidated"] == 1
        assert fb_gm.fallback_graph.nodes["e1"]["invalid_at"] == result["invalid_at"]

    def test_cascade_invalidates_edges(self, fb_gm):
        _seed(fb_gm)
        result = fb_gm.delete_entity("e1", cascade=True)
        assert result["relations_invalidated"] == 1
        assert fb_gm.fallback_graph.edges["e1", "e2"]["invalid_at"] == result["invalid_at"]

    def test_no_cascade_leaves_edges_active(self, fb_gm):
        _seed(fb_gm)
        result = fb_gm.delete_entity("e1", cascade=False)
        assert result["relations_invalidated"] == 0
        assert "invalid_at" not in fb_gm.fallback_graph.edges["e1", "e2"]

    def test_not_found_returns_error(self, fb_gm):
        _seed(fb_gm)
        result = fb_gm.delete_entity("nope")
        assert result["status"] == "error"
        assert "nope" in result["message"]

    def test_idempotent_second_delete_is_noop(self, fb_gm):
        _seed(fb_gm)
        fb_gm.delete_entity("e1")
        second = fb_gm.delete_entity("e1")
        assert second["status"] == "success"
        assert second["entities_invalidated"] == 0
        assert second["relations_invalidated"] == 0

    def test_workspace_mismatch_returns_error(self, fb_gm):
        fb_gm.fallback_graph.add_node("e1", entity_type="Agent", workspace_id="ws1")
        result = fb_gm.delete_entity("e1", workspace_id="ws2")
        assert result["status"] == "error"

    def test_invalidates_query_cache(self, fb_gm):
        _seed(fb_gm)
        fb_gm._query_cache["stale"] = [{"id": "e1"}]
        fb_gm._query_cache_timestamps["stale"] = 1.0
        fb_gm.delete_entity("e1")
        assert fb_gm._query_cache == {}


class TestDeleteEntityNeo4j:
    def _neo4j_gm(self):
        with patch.object(GraphManager, "_connect"):
            gm = GraphManager.__new__(GraphManager)
            gm._test_mode = False
            gm._connected = True
            gm._use_fallback = False
            gm._mode = "neo4j_driver"
            gm.graph = None
            gm.fallback_graph = None
            gm._query_cache = {}
            gm._query_cache_timestamps = {}
            gm._temporal_index = {}
            gm._temporal_index_built = False
            gm.neo4j_driver = MagicMock()
            # 单例卫生：同 fb_gm，避免审计通道构造 GraphManager() 复位 neo4j_driver/_mode
            GraphManager._instance = gm
            GraphManager._initialized = True
            return gm

    def test_sets_invalid_at_cypher(self):
        gm = self._neo4j_gm()
        session = MagicMock()
        gm.neo4j_driver.session.return_value.__enter__.return_value = session
        # 探测存在 -> count=1；SET 节点；cascade 边 count=2
        session.run.side_effect = [
            MagicMock(single=lambda: {"cnt": 1}),   # 存在性探测
            MagicMock(),                            # SET 节点
            MagicMock(single=lambda: {"invalidated": 2}),  # cascade 边计数
        ]
        result = gm.delete_entity("e1")
        assert result["status"] == "success"
        assert result["relations_invalidated"] == 2
        cyphers = " ".join(str(c.args[0]) for c in session.run.call_args_list)
        assert "invalid_at" in cyphers

    def test_not_found_when_count_zero(self):
        gm = self._neo4j_gm()
        session = MagicMock()
        gm.neo4j_driver.session.return_value.__enter__.return_value = session
        session.run.return_value.single.return_value = {"cnt": 0}
        result = gm.delete_entity("e1")
        assert result["status"] == "error"

    def test_driver_exception_returns_error(self):
        gm = self._neo4j_gm()
        gm.neo4j_driver.session.side_effect = RuntimeError("boom")
        result = gm.delete_entity("e1")
        assert result["status"] == "error"
        assert "boom" in result["message"]
