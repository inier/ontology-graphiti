"""GraphAnalyticsService — 图分析统一门面（ADR-078）。

依据 GraphManager.mode 选择后端：
- graphiti / neo4j_driver → GDSAnalyticsBackend（生产）
- fallback → NetworkXAnalyticsBackend（回退）
- unavailable → 返回错误（不降级）

统一 API：centrality / community / link_prediction / shortest_path。
"""

from __future__ import annotations

import logging
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)


class GraphAnalyticsService:
    """图分析服务门面"""

    def __init__(self, graph_manager=None):
        from odap.infra.graph.graph_service import GraphManager
        self.graph_manager = graph_manager or GraphManager()

    # ── 后端选择 ──

    def _backend(self):
        """按 mode 选择后端"""
        mode = self.graph_manager.mode
        if mode in ("graphiti", "neo4j_driver"):
            from .gds_backend import GDSAnalyticsBackend
            if self.graph_manager.neo4j_driver is None:
                raise RuntimeError("Neo4j 模式但 driver 未初始化")
            return GDSAnalyticsBackend(self.graph_manager.neo4j_driver)
        if mode == "fallback":
            from .networkx_backend import NetworkXAnalyticsBackend
            return NetworkXAnalyticsBackend()
        raise RuntimeError(f"图数据库不可用（mode={mode}），图分析拒绝服务")

    # ── 统一 API ──

    def centrality(
        self,
        metric: str = "degree",
        top_k: int = 10,
        workspace_id: str = "default",
    ) -> Dict[str, Any]:
        """中心性分析"""
        backend = self._backend()
        # networkx 后端需要显式传图；GDS 后端用 graph_name
        from .networkx_backend import NetworkXAnalyticsBackend
        if isinstance(backend, NetworkXAnalyticsBackend):
            graph = self._get_fallback_graph(workspace_id)
            return backend.centrality(graph, metric=metric, top_k=top_k)
        return backend.centrality(
            graph_name="odap_analytics", metric=metric, workspace_id=workspace_id, top_k=top_k,
        )

    def community(
        self,
        algo: str = "louvain",
        workspace_id: str = "default",
    ) -> Dict[str, Any]:
        """社区发现"""
        backend = self._backend()
        from .networkx_backend import NetworkXAnalyticsBackend
        if isinstance(backend, NetworkXAnalyticsBackend):
            graph = self._get_fallback_graph(workspace_id)
            return backend.community(graph, algo=algo)
        return backend.community(graph_name="odap_analytics", algo=algo, workspace_id=workspace_id)

    def link_prediction(
        self,
        source: str,
        target: str,
        workspace_id: str = "default",
    ) -> Dict[str, Any]:
        """链路预测"""
        backend = self._backend()
        from .networkx_backend import NetworkXAnalyticsBackend
        if isinstance(backend, NetworkXAnalyticsBackend):
            graph = self._get_fallback_graph(workspace_id)
            return backend.link_prediction(graph, source, target)
        # GDS 后端无独立 link_prediction，降级 networkx（读同一图）
        graph = self._get_fallback_graph(workspace_id)
        from .networkx_backend import NetworkXAnalyticsBackend as NX
        return NX().link_prediction(graph, source, target)

    def shortest_path(
        self,
        source: str,
        target: str,
        weighted: bool = False,
        workspace_id: str = "default",
    ) -> Dict[str, Any]:
        """最短路径"""
        backend = self._backend()
        from .networkx_backend import NetworkXAnalyticsBackend
        if isinstance(backend, NetworkXAnalyticsBackend):
            graph = self._get_fallback_graph(workspace_id)
            return backend.shortest_path(graph, source, target, weighted=weighted)
        return backend.shortest_path(source, target, workspace_id=workspace_id)

    # ── 辅助 ──

    def _get_fallback_graph(self, workspace_id: str = "default"):
        """从 GraphManager 获取 fallback 图并按 workspace 过滤"""
        from .networkx_backend import NetworkXAnalyticsBackend
        gm = self.graph_manager
        graph = getattr(gm, "fallback_graph", None)
        if graph is None:
            raise RuntimeError("fallback_graph 未初始化")
        return NetworkXAnalyticsBackend.filter_by_workspace(graph, workspace_id)


_instance: Optional[GraphAnalyticsService] = None


def get_analytics_service() -> GraphAnalyticsService:
    """获取图分析服务单例"""
    global _instance
    if _instance is None:
        _instance = GraphAnalyticsService()
    return _instance


__all__ = ["GraphAnalyticsService", "get_analytics_service"]
