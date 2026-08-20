"""TDD 单元测试：ADR-078 图分析服务（networkx 回退后端）。

覆盖：
  T-ANA-1: centrality degree（中心性 top 排序）
  T-ANA-2: centrality pagerank
  T-ANA-3: community louvain（社区数 > 0）
  T-ANA-4: community label_propagation
  T-ANA-5: link_prediction 共同邻居 / Jaccard / Adamic-Adar / 优先连接
  T-ANA-6: shortest_path 无权 BFS
  T-ANA-7: shortest_path 不存在路径（length=-1）
  T-ANA-8: workspace 隔离过滤（filter_by_workspace）
"""

from __future__ import annotations

import networkx as nx
import pytest

from odap.infra.graph.analytics.networkx_backend import NetworkXAnalyticsBackend


@pytest.fixture
def backend():
    return NetworkXAnalyticsBackend()


@pytest.fixture
def graph():
    """标准无向图：三角形 + 悬挂节点"""
    g = nx.Graph()
    g.add_nodes_from(["a", "b", "c", "d", "e", "f"])
    g.add_edges_from([
        ("a", "b"), ("b", "c"), ("c", "a"),  # 三角形 a-b-c
        ("c", "d"), ("d", "e"),               # 链 c-d-e
        ("e", "f"),
    ])
    return g


class TestCentrality:
    def test_degree_centrality(self, backend, graph):
        result = backend.centrality(graph, metric="degree", top_k=3)
        assert result["metric"] == "degree"
        # c 度最高（连 a,b,d）= 3
        top_node = result["top"][0]["node"]
        assert top_node == "c"
        assert len(result["top"]) == 3

    def test_pagerank(self, backend, graph):
        result = backend.centrality(graph, metric="pagerank", top_k=5)
        assert result["metric"] == "pagerank"
        assert len(result["top"]) > 0
        # 所有分数 > 0
        assert all(item["score"] > 0 for item in result["top"])

    def test_invalid_metric(self, backend, graph):
        with pytest.raises(ValueError):
            backend.centrality(graph, metric="unknown")


class TestCommunity:
    def test_louvain(self, backend, graph):
        result = backend.community(graph, algo="louvain")
        assert result["algo"] == "louvain"
        assert result["community_count"] >= 1
        # 所有节点被划分
        total_nodes = sum(c["size"] for c in result["communities"])
        assert total_nodes == graph.number_of_nodes()

    def test_label_propagation(self, backend, graph):
        result = backend.community(graph, algo="label_propagation")
        assert result["community_count"] >= 1

    def test_invalid_algo(self, backend, graph):
        with pytest.raises(ValueError):
            backend.community(graph, algo="unknown")


class TestLinkPrediction:
    def test_common_neighbors(self, backend, graph):
        # a 和 d 共同邻居 = c
        result = backend.link_prediction(graph, "a", "d")
        assert result["common_neighbors"] == 1
        assert result["jaccard"] > 0

    def test_no_common_neighbors(self, backend, graph):
        # a 和 f 无共同邻居
        result = backend.link_prediction(graph, "a", "f")
        assert result["common_neighbors"] == 0
        assert result["jaccard"] == 0.0


class TestShortestPath:
    def test_shortest_path_exists(self, backend, graph):
        result = backend.shortest_path(graph, "a", "f")
        assert result["length"] == 4  # a-b-c-d-e-f
        assert result["path"][0] == "a"
        assert result["path"][-1] == "f"

    def test_shortest_path_not_exists(self, backend, graph):
        g = nx.Graph()
        g.add_nodes_from(["x", "y"])
        result = backend.shortest_path(g, "x", "y")
        assert result["length"] == -1
        assert result["path"] == []


class TestWorkspaceIsolation:
    def test_filter_by_workspace(self, backend):
        g = nx.Graph()
        g.add_node("n1", workspace_id="ws1")
        g.add_node("n2", workspace_id="ws2")
        g.add_node("n3", workspace_id="ws1")
        g.add_edge("n1", "n2")
        g.add_edge("n1", "n3")

        sub = backend.filter_by_workspace(g, "ws1")
        assert "n1" in sub
        assert "n3" in sub
        assert "n2" not in sub  # ws2 被隔离

    def test_filter_default_workspace(self, backend):
        g = nx.Graph()
        g.add_node("n1")  # 无 workspace_id → default
        g.add_node("n2", workspace_id="ws2")
        sub = backend.filter_by_workspace(g, "default")
        assert "n1" in sub
        assert "n2" not in sub
