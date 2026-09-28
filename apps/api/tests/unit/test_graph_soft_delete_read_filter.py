"""软删除后 fallback 读路径必须排除失效实体（真实函数体）。

fallback 分支走真实 GraphManager（规则 14 #6）；Neo4j 分支用 mock driver 断言 Cypher。
"""
import networkx as nx
import pytest
from collections import deque
from unittest.mock import patch, MagicMock
from odap.infra.graph.graph_service import GraphManager
from odap.infra.graph._soft_delete import now_iso


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

    def test_traverse_excludes_invalidated_edges(self, fb_gm):
        """_traverse_fallback 边 guard：失效边不出现在遍历结果，活跃边保留。

        两个失效场景叠加：
        - e2 经 delete_entity(cascade=True) 失效（边+节点同时失效，双 guard）
        - e1→e3 边仅边失效、e3 节点仍活跃（存储层直写 invalid_at），
          专门命中 `if not is_active(edge_data): continue` 边 guard
          （cascade 场景下节点 guard 会掩护边 guard，无法单独验证）
        """
        _seed(fb_gm)
        # 补活跃边：e1→e3（后将仅失效边）、e1→e4（全程活跃，保留侧断言对象）
        fb_gm.fallback_graph.add_edge("e1", "e3", relationship="LINKS")
        fb_gm.fallback_graph.add_node("e4", entity_type="Tool", name="D")
        fb_gm.fallback_graph.add_edge("e1", "e4", relationship="USES")
        fb_gm.delete_entity("e2", cascade=True)
        # 存储层直写：仅失效 e1→e3 边，e3 节点保持活跃 -> 单独命中边 guard
        fb_gm.fallback_graph.edges["e1", "e3"]["invalid_at"] = now_iso()
        res = fb_gm.traverse("e1", max_depth=3)
        pairs = {(e["source"], e["target"]) for e in res["edges"]}
        # 排除侧：cascade 失效边 (e1,e2)、(e2,e3) 及任何触及 e2 的边均不出现
        assert ("e1", "e2") not in pairs
        assert ("e2", "e3") not in pairs
        assert all("e2" not in p for p in pairs)
        # 排除侧：仅边失效的 (e1,e3) 也被边 guard 排除（节点 e3 仍活跃）
        assert ("e1", "e3") not in pairs
        # 保留侧：活跃边 (e1,e4) 仍在遍历结果中
        assert ("e1", "e4") in pairs

    def test_get_entity_relations_excludes_invalidated_edges(self, fb_gm):
        """_get_entity_relations_fallback 边 guard：失效出边被排除，活跃出边保留。

        该方法只有边 guard（无节点 guard），cascade 失效边即直接命中。
        """
        _seed(fb_gm)
        fb_gm.fallback_graph.add_edge("e1", "e3", relationship="LINKS")
        fb_gm.delete_entity("e2", cascade=True)
        rels = fb_gm.get_entity_relations("e1")
        targets = {r["target"] for r in rels}
        # 排除侧：e1→e2 已失效，不得出现
        assert "e2" not in targets
        assert not any(r["target"] == "e2" and r["direction"] == "out" for r in rels)
        # 保留侧：活跃出边 e1→e3 保留
        assert any(
            r["target"] == "e3" and r["direction"] == "out" and r["type"] == "LINKS"
            for r in rels
        )

    def test_get_neighbors_excludes_invalidated_edge_cascade(self, fb_gm):
        """_get_neighbors_fallback 边 guard 分支：边失效即排除邻居。

        与 test_get_neighbors_excludes_deleted_neighbor（cascade=False，命中节点 guard）
        互补。cascade=True 下边与节点同时失效会互相掩护，故另加"仅边失效、
        节点活跃"的 e1→e3 场景（存储层直写 invalid_at），单独命中边 guard。
        """
        _seed(fb_gm)
        fb_gm.fallback_graph.add_edge("e1", "e3", relationship="LINKS")
        fb_gm.fallback_graph.add_node("e4", entity_type="Tool", name="D")
        fb_gm.fallback_graph.add_edge("e1", "e4", relationship="USES")
        fb_gm.delete_entity("e2", cascade=True)
        # 仅失效 e1→e3 边，e3 节点保持活跃 -> 单独命中边 guard
        fb_gm.fallback_graph.edges["e1", "e3"]["invalid_at"] = now_iso()
        neigh = fb_gm.get_neighbors("e1")
        ids = {n["id"] for n in neigh}
        assert "e2" not in ids          # cascade 失效（边+节点）
        assert "e3" not in ids          # 仅边失效，命中边 guard
        assert "e4" in ids              # 保留侧：活跃邻居仍在


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
