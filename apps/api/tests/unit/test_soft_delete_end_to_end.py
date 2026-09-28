"""端到端：软删除真实链路测试（proxy -> fallback GraphManager）。

不 mock SUT（规则 14 #6）：GraphWriteProxy、GraphManager.delete_entity、
get_entity、get_entity_relations 全部走真实函数体；仅在 GraphManager 单例
注入 fallback 实例（patch _connect + __new__ 手工装配，属下游存储边界）。

第二条用例是 Task 3 修复的回归护栏：cascade 原用 g.edges(entity_id)
（DiGraph 只返回出边），删除仅有入边的节点时入边永不失效；现已改为
in_edges + out_edges 并集。断言 relations_invalidated == 1 即守护此路径。
"""
import networkx as nx
import pytest
from unittest.mock import patch

from odap.infra.graph.graph_service import GraphManager


@pytest.fixture
def fb_gm_singleton():
    """把 GraphManager 单例替换为真实 fallback 实例（含 e1），并重置 proxy 单例。"""
    from odap.infra.query import graph_write_proxy as gwp

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
        gm.fallback_graph.add_node("e1", entity_type="Agent", name="A", workspace_id="ws1")
        GraphManager._instance = gm
        GraphManager._initialized = True
        # 重置 proxy 两级单例：模块级 _write_proxy_instance 与类级 _instance
        # 均需清空，否则 __new__ 会复用旧 proxy，其 _graph_manager 仍缓存
        # 上一条测试的 GM 实例，导致本测试写入错误的图。
        gwp._write_proxy_instance = None
        gwp.GraphWriteProxy._instance = None
        yield gm
        GraphManager._instance = None
        GraphManager._initialized = False
        gwp._write_proxy_instance = None
        gwp.GraphWriteProxy._instance = None


def test_executor_delete_soft_deletes_via_real_chain(fb_gm_singleton):
    """proxy.delete_entity -> 真实 GM.delete_entity：节点打 invalid_at，默认读路径不可见。"""
    from odap.infra.query import graph_write_proxy as gwp
    gwp._write_proxy_instance = None  # 重置 proxy 单例，令其重新 _get_graph_manager
    proxy = gwp.get_graph_write_proxy()

    result = proxy.delete_entity("e1", workspace_id="ws1")
    assert result["status"] == "success"
    assert fb_gm_singleton.fallback_graph.nodes["e1"]["invalid_at"] == result["invalid_at"]
    # 软删后默认读路径不可见
    assert fb_gm_singleton.get_entity("e1") is None
    gwp._write_proxy_instance = None


def test_delete_entity_invalidates_inbound_edges_via_real_chain(fb_gm_singleton):
    """回归护栏（Task 3）：仅有入边的节点被删时，入边必须级联失效。

    旧实现 cascade 用 g.edges(entity_id)（DiGraph 只返回出边），此场景
    relations_invalidated 会得 0 且入边永不失效。
    """
    gm = fb_gm_singleton
    gm.fallback_graph.add_node("e_src", entity_type="Agent", name="S", workspace_id="ws1")
    gm.fallback_graph.add_node("e_tgt", entity_type="Agent", name="T", workspace_id="ws1")
    # e_tgt 只有入边、无出边
    gm.fallback_graph.add_edge("e_src", "e_tgt", relationship="RELATES_TO")

    # 删除前：真实读路径能看到该入边
    rels = gm.get_entity_relations("e_tgt")
    assert len(rels) == 1
    assert rels[0]["direction"] == "in"
    assert rels[0]["target"] == "e_src"

    from odap.infra.query import graph_write_proxy as gwp
    gwp._write_proxy_instance = None
    proxy = gwp.get_graph_write_proxy()

    result = proxy.delete_entity("e_tgt", workspace_id="ws1")
    assert result["status"] == "success"
    # 关键断言：旧的出边-only 代码此处会得 0
    assert result["relations_invalidated"] == 1
    # 入边 data 已打 invalid_at，与节点同一时间戳
    assert gm.fallback_graph.edges["e_src", "e_tgt"]["invalid_at"] == result["invalid_at"]
    # 软删后默认读路径不再返回该入边
    assert gm.get_entity_relations("e_tgt") == []
    gwp._write_proxy_instance = None
