"""RetrievalService — 检索编排服务 (spec 008 / FR-001/003/005/006).

装配各检索引擎 + UnifiedRouter，对路由层提供统一入口。
不新建接口（Constitution IV）；函数 ≤40 行（Constitution I）。
"""

import logging
from typing import Any, Dict, Optional

from ..impl.chain_engine import ChainEngine
from ..impl.graph_engine import GraphEngine
from ..impl.hybrid_orchestrator import HybridOrchestrator
from ..impl.mdl_engine import MdlEngine
from ..impl.metric_engine import MetricEngine
from ..impl.nl_engine import NLEngine
from ..impl.reasoning_persistence_service import ReasoningPersistenceService
from ..impl.unified_router import UnifiedRouter
from ..models.schemas import SearchRequest, SearchResult
from ..storage.audit_log import audit_retrieval

logger = logging.getLogger("semantic_retrieval.service")


def _default_he_adapter() -> Any:
    """懒加载 HEAdapter 单例（hyperextract 未安装也不崩溃）。"""
    try:
        from odap.biz.data.hyper_extract.impl.he_adapter import HEAdapter

        return HEAdapter()
    except Exception:  # noqa: BLE001 — HE 模块缺失时返回 None，MdlEngine 自动降级
        return None


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
        he_adapter: Any = None,
        persistence: Optional[ReasoningPersistenceService] = None,
    ):
        self._graph = graph_engine or GraphEngine()
        self._nl = nl_engine or NLEngine(graph_engine=self._graph)
        self._metric = metric_engine or MetricEngine()
        self._chain = chain_engine or ChainEngine()
        he = he_adapter if he_adapter is not None else _default_he_adapter()
        self._mdl = mdl_engine or MdlEngine(he_adapter=he)
        self._persistence = persistence  # opt-in（默认 None，不持久化）
        engines = {
            "nl": self._nl,
            "graph": self._graph,
            "metric": self._metric,
            "chain": self._chain,
            "mdl": self._mdl,
        }
        self._router = unified_router or UnifiedRouter(engines=engines)
        self._hybrid = HybridOrchestrator(engines=engines)

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
        persist_candidates: bool = False,
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
        if persist_candidates and self._persistence:
            raw["candidates_meta"] = self._safe_persist(raw, workspace_id)
        return raw

    async def mdl_search(
        self, workspace_id: str, *, query: str,
        persist_candidates: bool = False,
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
        if persist_candidates and self._persistence:
            raw["candidates_meta"] = self._safe_persist(raw, workspace_id)
        return raw

    def _safe_persist(
        self, result: Dict[str, Any], workspace_id: str
    ) -> Dict[str, Any]:
        """持久化失败不阻断推理返回（fire-and-forget + 日志，设计 §6.1）。"""
        try:
            return self._persistence.persist(result, workspace_id)  # type: ignore[union-attr]
        except Exception as exc:  # noqa: BLE001 — 兜底双保险
            logger.warning("推理结论持久化失败: %s", exc)
            return {"persisted_count": 0, "error": str(exc)}

    async def hybrid_search(
        self,
        workspace_id: str,
        components: list,
        *,
        merge: str = "concat",
    ) -> Dict[str, Any]:
        """混合检索编排 (FR-007/008 / US4)：多组件顺序执行 + on_failure 容错。"""
        raw = await self._hybrid.orchestrate(
            workspace_id, components, merge=merge
        )
        audit_retrieval(
            "hybrid_search",
            details={
                "components": len(components),
                "rows": raw["total"],
                "warnings": len(raw["warnings"]),
            },
        )
        return raw
