"""RetrievalService — 检索编排服务 (spec 008 / FR-001/003/005).

装配各检索引擎 + UnifiedRouter，对路由层提供统一入口。
不新建接口（Constitution IV）；函数 ≤40 行（Constitution I）。
"""

import logging
from typing import Any, Dict

from ..impl.graph_engine import GraphEngine
from ..impl.nl_engine import NLEngine
from ..impl.unified_router import UnifiedRouter
from ..models.schemas import SearchRequest, SearchResult
from ..storage.audit_log import audit_retrieval

logger = logging.getLogger("semantic_retrieval.service")


class RetrievalService:
    """检索编排：统一/分项入口装配。"""

    def __init__(
        self,
        graph_engine: Any = None,
        nl_engine: Any = None,
        unified_router: Any = None,
    ):
        self._graph = graph_engine or GraphEngine()
        self._nl = nl_engine or NLEngine(graph_engine=self._graph)
        self._router = unified_router or UnifiedRouter(
            engines={"nl": self._nl, "graph": self._graph}
        )

    async def search(self, workspace_id: str, request: SearchRequest) -> SearchResult:
        """统一检索入口（FR-001）：按 request.mode 路由。"""
        raw = await self._router.route(
            workspace_id, request.query, mode=request.mode, limit=request.limit
        )
        audit_retrieval(
            "query",
            details={
                "mode": raw["mode"],
                "rows": raw["total"],
                "query_len": len(request.query),
            },
        )
        return SearchResult(
            query=request.query,
            mode=raw["mode"],
            total=raw["total"],
            rows=raw["rows"],
            explain=raw.get("explain"),
        )

    async def graph_search(
        self, workspace_id: str, query: str, limit: int = 20
    ) -> Dict[str, Any]:
        """分项：图检索（FR-005）。"""
        raw = await self._graph.search(workspace_id, query, limit=limit)
        audit_retrieval("graph_search", details={"rows": raw["total"], "query_len": len(query)})
        return raw

    async def nl_search(
        self, workspace_id: str, query: str, limit: int = 20
    ) -> Dict[str, Any]:
        """分项：自然语言检索 + USL 消歧（FR-003/FR-016）。"""
        raw = await self._nl.search(workspace_id, query, limit=limit)
        audit_retrieval("nl_search", details={"rows": raw["total"], "query_len": len(query)})
        return raw
