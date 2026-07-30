"""RetrievalService — 检索编排服务 (spec 008 / FR-001/003/005/006).

装配各检索引擎 + UnifiedRouter，对路由层提供统一入口。
不新建接口（Constitution IV）；函数 ≤40 行（Constitution I）。
"""

import logging
from typing import Any, Dict, Optional

from ..impl.chain_engine import ChainEngine
from ..impl.graph_engine import GraphEngine
from ..impl.mdl_engine import MdlEngine
from ..impl.metric_engine import MetricEngine
from ..impl.nl_engine import NLEngine
from ..impl.unified_router import UnifiedRouter
from ..models.schemas import SearchRequest, SearchResult
from ..storage.audit_log import audit_retrieval

logger = logging.getLogger("semantic_retrieval.service")


class RetrievalService:
    """检索编排：统一/分项/指标 入口装配。"""

    def __init__(
        self,
        graph_engine: Any = None,
        nl_engine: Any = None,
        metric_engine: Any = None,
        chain_engine: Any = None,
        mdl_engine: Any = None,
        unified_router: Any = None,
    ):
        self._graph = graph_engine or GraphEngine()
        self._nl = nl_engine or NLEngine(graph_engine=self._graph)
        self._metric = metric_engine or MetricEngine()
        self._chain = chain_engine or ChainEngine()
        self._mdl = mdl_engine or MdlEngine()
        engines = {
            "nl": self._nl,
            "graph": self._graph,
            "metric": self._metric,
            "chain": self._chain,
            "mdl": self._mdl,
        }
        self._router = unified_router or UnifiedRouter(engines=engines)

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

    async def metric_search(
        self,
        workspace_id: str,
        metric: str,
        *,
        object_type: Optional[str] = None,
        granularity: Optional[str] = None,
        time_window: Optional[Dict[str, Any]] = None,
        limit: int = 20,
    ) -> Dict[str, Any]:
        """分项：指标查询 (FR-006 / US2 BI 工具)。"""
        raw = await self._metric.metric(
            workspace_id,
            metric,
            object_type=object_type,
            granularity=granularity,
            time_window=time_window,
            limit=limit,
        )
        audit_retrieval(
            "metric_search",
            details={"metric": metric, "rows": raw["total"], "limit": limit},
        )
        return raw

    async def chain_search(
        self,
        workspace_id: str,
        *,
        query: str,
        rules: Optional[list] = None,
        max_depth: int = 5,
    ) -> Dict[str, Any]:
        """分项：链式推理 + 循环检测 (FR-004/FR-014 / US3)。"""
        raw = await self._chain.reason(
            workspace_id,
            query=query,
            rules=rules or [],
            max_depth=max_depth,
        )
        audit_retrieval(
            "chain_search",
            details={
                "rows": raw["total"],
                "cycle": raw["reasoning"]["cycle_detected"],
                "depth": max_depth,
            },
        )
        return raw

    async def mdl_search(
        self, workspace_id: str, *, query: str
    ) -> Dict[str, Any]:
        """分项：MDL/DSL 推理 (FR-004 / US3 / Q6: 不发明 DSL，复用 HE 模板)。"""
        raw = await self._mdl.reason(workspace_id, query=query)
        audit_retrieval(
            "mdl_search",
            details={
                "template": raw["reasoning"]["template"],
                "status": raw["reasoning"]["status"],
            },
        )
        return raw
