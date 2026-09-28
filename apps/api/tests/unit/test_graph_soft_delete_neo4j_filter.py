"""Neo4j 读路径 Cypher 必须含 invalid_at IS NULL 谓词（mock driver）。"""
from unittest.mock import patch, MagicMock
from odap.infra.graph.graph_service import GraphManager


def _neo4j_gm():
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
        # query_entities 走缓存统计计数器（__init__ 被绕过，需手工补齐）
        gm.cache_hits = 0
        gm.cache_misses = 0
        # query_entities finally 块与断路器状态所需属性
        gm.query_times = []
        gm.failure_count = 0
        gm.failure_threshold = 5
        gm.last_failure_time = None
        gm.circuit_open = False
        gm._temporal_index = {}
        gm._temporal_index_built = False
        gm.neo4j_driver = MagicMock()
        return gm


def _session_returning(gm, records=None, single=None):
    session = MagicMock()
    gm.neo4j_driver.session.return_value.__enter__.return_value = session
    run_result = MagicMock()
    run_result.__iter__.return_value = iter(records or [])
    run_result.single.return_value = single
    session.run.return_value = run_result
    return session


def test_get_entity_neo4j_filters_invalid_at():
    gm = _neo4j_gm()
    session = _session_returning(gm, single=None)
    gm.get_entity("e1")
    cypher = str(session.run.call_args.args[0])
    assert "invalid_at IS NULL" in cypher


def test_get_entity_include_deleted_neo4j_no_filter():
    gm = _neo4j_gm()
    session = _session_returning(gm, single=None)
    gm.get_entity("e1", include_deleted=True)
    cypher = str(session.run.call_args.args[0])
    assert "invalid_at IS NULL" not in cypher


def test_query_entities_neo4j_filters_invalid_at():
    gm = _neo4j_gm()
    session = _session_returning(gm, records=[])
    gm.query_entities(entity_type="Agent")
    cypher = str(session.run.call_args.args[0])
    assert "invalid_at IS NULL" in cypher


def test_search_neo4j_filters_invalid_at():
    gm = _neo4j_gm()
    session = _session_returning(gm, records=[])
    gm.search("x")
    cypher = str(session.run.call_args.args[0])
    assert "invalid_at IS NULL" in cypher


def test_get_all_relations_neo4j_filters_invalid_edges():
    gm = _neo4j_gm()
    session = _session_returning(gm, records=[])
    gm.get_all_relations()
    cypher = str(session.run.call_args.args[0])
    assert "invalid_at IS NULL" in cypher
