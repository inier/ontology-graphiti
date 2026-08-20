"""图分析服务（ADR-078）。

- service:            GraphAnalyticsService 统一门面（按 GraphManager.mode 选后端）
- networkx_backend:   networkx 回退实现（零依赖，开发/测试可用）
- gds_backend:        Neo4j GDS 后端（生产，Cypher 投影）
- api/routes:         图分析 REST API（按 workspace 隔离）
"""

from .service import GraphAnalyticsService, get_analytics_service
from .networkx_backend import NetworkXAnalyticsBackend

__all__ = [
    "GraphAnalyticsService",
    "get_analytics_service",
    "NetworkXAnalyticsBackend",
]
