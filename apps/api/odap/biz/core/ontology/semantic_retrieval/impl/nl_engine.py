"""NL 检索引擎 (spec 008 / US1 / FR-016 USL 术语消歧)。

职责：
1. 调用 USL list_terms(synonym_keyword=query) 做业务术语消歧（FR-016）
2. 将（消歧后的）查询交给 GraphEngine 检索实体/关系
3. 返回统一结构 {rows, total, explain}

降级策略（project_memory：包独立性 + 应用层适配）：
- USL 未实现/不可用时 → 透传原查询，explain.usl=None，不阻断检索
- USL 调用异常 → explain.usl={"status":"degraded"}，仍返回 graph 结果

Constitution IV：不新建接口；USL 通过懒加载可选注入。
"""

import logging
from typing import Any, Dict, Optional

logger = logging.getLogger("semantic_retrieval.nl_engine")

_UNSET = object()  # 哨兵：区分"未提供（懒加载）"与"显式禁用(None)"


class NLEngine:
    """自然语言检索：USL 消歧 + 图检索。"""

    def __init__(self, graph_engine=_UNSET, usl_manager=_UNSET):
        self._graph = graph_engine
        self._usl = usl_manager

    async def search(
        self,
        workspace_id: str,
        query: str,
        limit: int = 20,
    ) -> Dict[str, Any]:
        """NL 检索主入口。"""
        usl = self._get_usl()
        usl_info = self._resolve_term(query, usl)
        graph = self._get_graph()
        graph_result = await graph.search(workspace_id, query, limit=limit)
        return {
            "rows": graph_result.get("rows", []),
            "total": graph_result.get("total", 0),
            "explain": {
                "source": "nl",
                "usl": usl_info,
                "graph": graph_result.get("explain"),
            },
        }

    # ------------------------------------------------------------------
    # USL 术语消歧（FR-016）
    # ------------------------------------------------------------------
    def _resolve_term(
        self,
        term_text: str,
        usl: Optional[Any],
    ) -> Optional[Dict[str, Any]]:
        """通过 USL 查询术语归属域；不可用/未命中返回 None，异常返回 degraded。"""
        if usl is None:
            return None
        try:
            terms, _total = usl.list_terms(synonym_keyword=term_text, page_size=5)
        except Exception as exc:
            logger.warning("USL disambiguation failed for %r: %s", term_text, exc)
            return {"status": "degraded"}
        if not terms:
            return None
        t = terms[0]
        return {
            "term_id": getattr(t, "term_id", None),
            "domain_id": getattr(t, "domain_id", None),
        }

    # ------------------------------------------------------------------
    # 懒加载访问器
    # ------------------------------------------------------------------
    def _get_graph(self):
        if self._graph is _UNSET:
            from .graph_engine import GraphEngine

            self._graph = GraphEngine()
        return self._graph

    def _get_usl(self):
        if self._usl is _UNSET:
            self._usl = self._load_usl()
        return self._usl

    @staticmethod
    def _load_usl():
        """懒加载 USL 管理服务；不可用时返回 None（透传降级）。"""
        try:
            from odap.biz.semantic_admin.usl_manager.services import UslManagerService

            return UslManagerService()
        except Exception as exc:
            logger.debug("USL manager unavailable, passthrough: %s", exc)
            return None
