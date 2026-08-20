"""GDSAnalyticsBackend — Neo4j GDS 后端（生产，ADR-078）。

依赖 Neo4j GDS 插件（服务器端安装）。使用 Cypher 投影按 workspace_id
隔离，再调用 GDS 算法（通过 Neo4j Driver 的 gds.* 过程）。

若 GDS 插件不可用，抛 RuntimeError（由 service 层决定是否降级 networkx）。
"""

from __future__ import annotations

import logging
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)


class GDSAnalyticsBackend:
    """Neo4j GDS 图分析后端（生产）"""

    def __init__(self, driver):
        self.driver = driver

    def _run_gds(self, cypher: str, **params) -> List[Dict[str, Any]]:
        """执行 GDS Cypher 并返回记录列表"""
        try:
            with self.driver.session() as session:
                result = session.run(cypher, **params)
                return [dict(r) for r in result]
        except Exception as e:
            raise RuntimeError(f"GDS 执行失败（可能未安装 GDS 插件）: {e}") from e

    def centrality(
        self,
        graph_name: str,
        metric: str = "degree",
        workspace_id: str = "default",
        top_k: int = 10,
    ) -> Dict[str, Any]:
        """中心性（GDS 投影 + 算法流式输出）"""
        projection = f"""
        CALL gds.graph.project(
            '{graph_name}',
            'Entity',
            '*',
            {{ nodeProperties: ['workspace_id'] }}
        )
        """
        algo_map = {
            "degree": "gds.degree.stream",
            "pagerank": "gds.pageRank.stream",
        }
        algo = algo_map.get(metric)
        if algo is None:
            raise ValueError(f"GDS 后端支持的中心性指标: {list(algo_map.keys())}，收到 {metric}")

        self._run_gds(projection)
        try:
            query = f"""
            CALL {algo}('{graph_name}', {{}})
            YIELD nodeId, score
            WITH gds.util.asNode(nodeId) AS n, score
            WHERE n.workspace_id = $ws
            RETURN n.id AS node, score
            ORDER BY score DESC
            LIMIT $top_k
            """
            rows = self._run_gds(query, ws=workspace_id, top_k=top_k)
            return {"metric": metric, "top": rows, "count": len(rows)}
        finally:
            self._run_gds(f"CALL gds.graph.drop('{graph_name}') YIELD graphName")

    def community(
        self,
        graph_name: str,
        algo: str = "louvain",
        workspace_id: str = "default",
    ) -> Dict[str, Any]:
        """社区发现（Louvain 流式）"""
        if algo != "louvain":
            raise ValueError(f"GDS 后端支持 louvain，收到 {algo}")
        projection = f"""
        CALL gds.graph.project(
            '{graph_name}', 'Entity', '*', {{ nodeProperties: ['workspace_id'] }}
        )
        """
        self._run_gds(projection)
        try:
            query = f"""
            CALL gds.louvain.stream('{graph_name}', {{}})
            YIELD nodeId, communityId
            WITH gds.util.asNode(nodeId) AS n, communityId
            WHERE n.workspace_id = $ws
            RETURN n.id AS node, communityId AS community
            ORDER BY communityId
            """
            rows = self._run_gds(query, ws=workspace_id)
            # 聚合为 community 结构
            communities: Dict[int, List[str]] = {}
            for r in rows:
                cid = int(r["community"])
                communities.setdefault(cid, []).append(str(r["node"]))
            result = [
                {"id": cid, "size": len(nodes), "nodes": nodes}
                for cid, nodes in sorted(communities.items())
            ]
            return {"algo": algo, "community_count": len(result), "communities": result}
        finally:
            self._run_gds(f"CALL gds.graph.drop('{graph_name}') YIELD graphName")

    def shortest_path(
        self,
        source: str,
        target: str,
        workspace_id: str = "default",
    ) -> Dict[str, Any]:
        """最短路径（Neo4j 内建 shortestPath，非 GDS）"""
        query = """
        MATCH (a:Entity {id: $src}), (b:Entity {id: $dst})
        WHERE a.workspace_id = $ws AND b.workspace_id = $ws
        MATCH p = shortestPath((a)-[*]-(b))
        RETURN [n IN nodes(p) | n.id] AS path, length(p) AS length
        """
        rows = self._run_gds(query, src=source, dst=target, ws=workspace_id)
        if not rows:
            return {"source": source, "target": target, "path": [], "length": -1}
        return {
            "source": source,
            "target": target,
            "path": [str(n) for n in rows[0]["path"]],
            "length": rows[0]["length"],
            "weighted": False,
        }


__all__ = ["GDSAnalyticsBackend"]
