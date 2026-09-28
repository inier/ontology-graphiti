"""软删除后 fallback 读路径必须排除失效实体（真实函数体）。

fallback 分支走真实 GraphManager（规则 14 #6）；Neo4j 分支用 mock driver 断言 Cypher。
"""
import networkx as nx
import pytest
from collections import deque
from unittest.mock import patch, MagicMock
from odap.infra.graph.graph_service import GraphManager


@pytest.fixture(autouse=True)
def _reset_gm_singleton():
    """GraphManager 是进程级单例；读路径成功时会经 graph_audit 再次构造 GraphManager()。

    每个用例前后重置单例与 _initialized，避免 __init__ 复位 fallback_graph
    造成的跨用例状态泄漏（对齐 test_graph_delete_entity.py 的既有惯用法）。
    """
    GraphManager._instance = None
    GraphManager._initialized = False
    GraphManager._test_mode = False
    yield
    GraphManager._instance = None
    GraphManager._initialized = False
    GraphManager._test_mode = False


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
        # query_entities 会走缓存与断路器统计，需补齐 __init__ 里对应的实例属性
        gm.cache_hits = 0
        gm.cache_misses = 0
        gm._cache_max_size = 256
        gm._cache_ttl = 300
        gm.query_times = deque(maxlen=100)
        gm.failure_threshold = 5
        gm.failure_count = 0
        gm.circuit_open = False
        gm.last_failure_time = 0
        # 单例卫生：让审计通道构造 GraphManager() 时命中 __init__ 的 _initialized 早退，
        # 避免其复位 fallback_graph（否则首个用例后续会读到被清空的图）。
        GraphManager._instance = gm
        GraphManager._initialized = True
        yield gm


def _seed(gm):
    gm.fallback_graph.add_node("e1", entity_type="Agent", name="A")
    gm.fallback_graph.add_node("e2", entity_type="Agent", name="B")
    gm.fallback_graph.add_node("e3", entity_type="Tool", name="C")
    gm.fallback_graph.add_edge("e1", "e2", relationship="DEPENDS_ON")
    gm.fallback_graph.add_edge("e2", "e3", relationship="USES")


class TestReadFilterAfterSoftDelete:
    def test_get_entity_excludes_deleted_by_default(self, fb_gm):
        _seed(fb_gm)
        fb_gm.delete_entity("e1", cascade=False)
        assert fb_gm.get_entity("e1") is None

    def test_get_entity_include_deleted_opt_in(self, fb_gm):
        _seed(fb_gm)
        fb_gm.delete_entity("e1", cascade=False)
        got = fb_gm.get_entity("e1", include_deleted=True)
        assert got is not None
        assert got["id"] == "e1"

    def test_query_entities_excludes_deleted(self, fb_gm):
        _seed(fb_gm)
        fb_gm.delete_entity("e1", cascade=False)
        ids = [e["id"] for e in fb_gm.query_entities(entity_type="Agent")]
        assert "e1" not in ids
        assert "e2" in ids

    def test_search_excludes_deleted(self, fb_gm):
        _seed(fb_gm)
        fb_gm.delete_entity("e1", cascade=False)
        hits = fb_gm.search("A")
        assert all(h["id"] != "e1" for h in hits)

    def test_get_all_relations_excludes_invalidated_edges(self, fb_gm):
        _seed(fb_gm)
        fb_gm.delete_entity("e1", cascade=True)
        rels = fb_gm.get_all_relations()
        pairs = {(r["source"], r["target"]) for r in rels}
        assert ("e1", "e2") not in pairs
        assert ("e2", "e3") in pairs

    def test_get_neighbors_excludes_deleted_neighbor(self, fb_gm):
        _seed(fb_gm)
        fb_gm.delete_entity("e2", cascade=False)
        neigh = fb_gm.get_neighbors("e1")
        assert all(n["id"] != "e2" for n in neigh)


def test_get_entity_neo4j_filters_and_opt_in():
    """预检裁定守护：Neo4j 模式下 get_entity 的 include_deleted 必须真正下推到 Cypher。

    include_deleted=False -> Cypher 含 "invalid_at IS NULL"（默认排除失效）
    include_deleted=True  -> Cypher 不含 "invalid_at IS NULL"（opt-in 读取失效）
    """
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
        GraphManager._instance = gm
        GraphManager._initialized = True

        session = MagicMock()
        gm.neo4j_driver.session.return_value.__enter__.return_value = session
        session.run.return_value.single.return_value = None

        gm.get_entity("e1", include_deleted=False)
        cypher_default = str(session.run.call_args.args[0])
        assert "invalid_at IS NULL" in cypher_default

        session.reset_mock()
        gm.get_entity("e1", include_deleted=True)
        cypher_optin = str(session.run.call_args.args[0])
        assert "invalid_at IS NULL" not in cypher_optin
