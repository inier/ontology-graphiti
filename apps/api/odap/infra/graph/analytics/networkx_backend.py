"""NetworkXAnalyticsBackend — networkx 回退图分析实现（ADR-078）。

零外部依赖（networkx 已在 GraphManager 回退路径使用）。
提供四类能力：centrality / community / link_prediction / shortest_path。

输入：networkx 图（DiGraph 或 Graph），节点可带 workspace_id 属性做隔离过滤。
"""

from __future__ import annotations

import logging
from typing import Any, Dict, List, Optional, Tuple

logger = logging.getLogger(__name__)


class NetworkXAnalyticsBackend:
    """networkx 图分析后端（回退）"""

    def __init__(self):
        pass

    # ── 中心性 ──

    def centrality(
        self,
        graph,
        metric: str = "degree",
        top_k: int = 10,
    ) -> Dict[str, Any]:
        """计算中心性指标。

        metric: degree | betweenness | closeness | eigenvector | pagerank
        """
        import networkx as nx

        if metric == "degree":
            scores = dict(nx.degree_centrality(graph))
        elif metric == "betweenness":
            scores = dict(nx.betweenness_centrality(graph))
        elif metric == "closeness":
            scores = dict(nx.closeness_centrality(graph))
        elif metric == "eigenvector":
            try:
                scores = dict(nx.eigenvector_centrality(graph, max_iter=1000))
            except Exception:
                scores = dict(nx.pagerank(graph))
        elif metric == "pagerank":
            scores = dict(nx.pagerank(graph))
        else:
            raise ValueError(f"不支持的中心性指标: {metric}")

        top = self._top_n(scores, top_k)
        return {"metric": metric, "top": top, "count": len(scores)}

    # ── 社区发现 ──

    def community(
        self,
        graph,
        algo: str = "louvain",
    ) -> Dict[str, Any]:
        """社区发现。

        algo: louvain | label_propagation | girvan_newman
        """
        import networkx as nx
        from networkx.algorithms.community import (
            greedy_modularity_communities,
            label_propagation_communities,
        )

        if algo == "louvain":
            communities = list(greedy_modularity_communities(graph))
        elif algo == "label_propagation":
            communities = list(label_propagation_communities(graph))
        elif algo == "girvan_newman":
            from networkx.algorithms.community import girvan_newman
            # 取第一层划分（边介数最高移除一次）
            comp = girvan_newman(graph)
            communities = list(next(comp))
        else:
            raise ValueError(f"不支持的社区算法: {algo}")

        result = [
            {"id": i, "size": len(c), "nodes": sorted(str(n) for n in c)}
            for i, c in enumerate(communities)
        ]
        return {"algo": algo, "community_count": len(result), "communities": result}

    # ── 链路预测 ──

    def link_prediction(
        self,
        graph,
        source: str,
        target: str,
    ) -> Dict[str, Any]:
        """链路预测（共同邻居 / Jaccard / Adamic-Adar / 优先连接）。

        对无向图使用 node 邻接；对 DiGraph 使用共同邻居（入+出合并）。
        """
        import networkx as nx

        def neighbors(g, n):
            if g.is_directed():
                return set(g.predecessors(n)) | set(g.successors(n))
            return set(g.neighbors(n))

        ns = neighbors(graph, source)
        nt = neighbors(graph, target)

        common = ns & nt
        common_count = len(common)

        # Jaccard
        union = ns | nt
        jaccard = common_count / len(union) if union else 0.0

        # Adamic-Adar
        aa = 0.0
        for z in common:
            nz = neighbors(graph, z)
            if len(nz) > 1:
                import math
                aa += 1.0 / math.log(len(nz))

        # 优先连接
        preferential = len(ns) * len(nt)

        return {
            "source": source,
            "target": target,
            "common_neighbors": common_count,
            "jaccard": round(jaccard, 4),
            "adamic_adar": round(aa, 4),
            "preferential_attachment": preferential,
        }

    # ── 最短路径 ──

    def shortest_path(
        self,
        graph,
        source: str,
        target: str,
        weighted: bool = False,
    ) -> Dict[str, Any]:
        """最短路径（Dijkstra 加权 / BFS 无权）"""
        import networkx as nx

        if source not in graph or target not in graph:
            return {"source": source, "target": target, "path": [], "length": -1}

        try:
            if weighted:
                path = nx.dijkstra_path(graph, source, target)
                length = nx.dijkstra_path_length(graph, source, target)
            else:
                path = nx.shortest_path(graph, source, target)
                length = len(path) - 1
        except nx.NetworkXNoPath:
            return {"source": source, "target": target, "path": [], "length": -1}

        return {
            "source": source,
            "target": target,
            "path": [str(n) for n in path],
            "length": length,
            "weighted": weighted,
        }

    # ── 辅助 ──

    @staticmethod
    def _top_n(scores: Dict[Any, float], top_k: int) -> List[Dict[str, Any]]:
        """取 top_k 高分区"""
        sorted_items = sorted(scores.items(), key=lambda kv: kv[1], reverse=True)
        return [
            {"node": str(node), "score": round(float(score), 6)}
            for node, score in sorted_items[:top_k]
        ]

    @staticmethod
    def filter_by_workspace(graph, workspace_id: str = "default"):
        """按 workspace_id 过滤子图（隔离）"""
        import networkx as nx

        nodes = [
            n for n, d in graph.nodes(data=True)
            if d.get("workspace_id", "default") == workspace_id
        ]
        return graph.subgraph(nodes).copy()


__all__ = ["NetworkXAnalyticsBackend"]
