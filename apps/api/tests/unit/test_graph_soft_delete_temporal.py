"""软删除后 query_temporal/state_at 的 as-of 上界正确性（13a Task 5）。

语义：valid_time <= vt < invalid_at；invalid_at 缺失/空 = 活跃。
测试均在索引模式下进行——fallback 模式（_use_fallback=True）时
query_temporal 在进入索引分支前就直接返回 query_entities，
手工塞入 _temporal_index 的数据会被完全忽略，故必须用索引模式 gm。
所有测试同步调用（query_temporal/state_at 均为同步 def），不打桩被测方法本身。
"""
import pytest
from unittest.mock import patch, MagicMock

from odap.infra.graph.graph_service import GraphManager


@pytest.fixture
def idx_gm():
    """索引模式 GraphManager：_connected=True、_use_fallback=False、
    _temporal_index_built=True（让 _build_temporal_index 早退，保留手工索引）。
    单例置位/重置防止 graph_audit 内部 GraphManager() 复位状态。
    """
    with patch.object(GraphManager, "_connect"):
        gm = GraphManager.__new__(GraphManager)
        gm._test_mode = False
        gm._connected = True
        gm._use_fallback = False
        gm._mode = "neo4j_driver"
        gm.graph = MagicMock()  # 索引分支在 async graphiti 查询前就 return，不会真正调用
        gm.neo4j_driver = MagicMock()
        gm.fallback_graph = None
        gm._query_cache = {}
        gm._query_cache_timestamps = {}
        # _cache_get/_cache_set 所需属性（__init__ 被绕过，手工补齐）
        gm.cache_hits = 0
        gm.cache_misses = 0
        gm._cache_max_size = 256
        gm._cache_ttl = 300
        gm._temporal_index = {}
        gm._temporal_index_built = True
        GraphManager._instance = gm
        GraphManager._initialized = True
        yield gm
        GraphManager._instance = None
        GraphManager._initialized = False


def _seed_index_with_invalid_at(gm):
    """塞入一条 2026-06-01 失效的索引项（结构与 _build_temporal_index 产物一致）。"""
    gm._temporal_index = {
        "2026-01-01T00:00:00+00:00": [
            {
                "id": "e1",
                "type": "Agent",
                "properties": {"name": "test"},
                "valid_time": "2026-01-01T00:00:00+00:00",
                "transaction_time": "2026-01-02T00:00:00+00:00",
                "invalid_at": "2026-06-01T00:00:00+00:00",
            },
        ]
    }
    gm._temporal_index_built = True


def test_query_temporal_excludes_after_invalid(idx_gm):
    """消费端：as-of 时刻在 invalid_at 之后，索引分支不得返回该实体。"""
    _seed_index_with_invalid_at(idx_gm)
    # vt 在失效之前 -> 可见
    before = idx_gm.query_temporal(valid_time="2026-03-01T00:00:00+00:00")
    assert any(e.get("id") == "e1" for e in before)
    # vt 在失效之后 -> 不可见（valid_time <= vt < invalid_at）
    after = idx_gm.query_temporal(valid_time="2026-09-01T00:00:00+00:00")
    assert not any(e.get("id") == "e1" for e in after)


def test_state_at_excludes_after_invalid(idx_gm):
    """state_at 经 query_temporal 同步获得上界过滤；返回 Dict，取 ["entities"]。"""
    _seed_index_with_invalid_at(idx_gm)
    assert any(
        e.get("id") == "e1"
        for e in idx_gm.state_at("2026-03-01T00:00:00+00:00")["entities"]
    )
    assert not any(
        e.get("id") == "e1"
        for e in idx_gm.state_at("2026-09-01T00:00:00+00:00")["entities"]
    )


def test_build_temporal_index_carries_invalid_at(idx_gm):
    """生产端：_build_temporal_index 真实函数体（仅在 neo4j driver 边界打桩），
    Cypher RETURN 必须带出 n.invalid_at，且索引项 dict 写入该字段（规则 14 #6）。
    """
    idx_gm._temporal_index = {}
    idx_gm._temporal_index_built = False
    session = MagicMock()
    idx_gm.neo4j_driver.session.return_value.__enter__.return_value = session
    record = {
        "id": "e1",
        "valid_time": "2026-01-01T00:00:00+00:00",
        "transaction_time": "2026-01-02T00:00:00+00:00",
        "invalid_at": "2026-06-01T00:00:00+00:00",
        "labels": ["Entity", "Agent"],
        "props": {"name": "test"},
    }
    run_result = MagicMock()
    run_result.__iter__.return_value = iter([record])
    session.run.return_value = run_result

    idx_gm._build_temporal_index()

    # (a) 下发的 Cypher 含 n.invalid_at
    cypher = str(session.run.call_args.args[0])
    assert "n.invalid_at" in cypher
    # (b) 构建出的索引项含 invalid_at 且值等于 record 中的值
    entry = idx_gm._temporal_index["2026-01-01T00:00:00+00:00"][0]
    assert "invalid_at" in entry
    assert entry["invalid_at"] == record["invalid_at"]
