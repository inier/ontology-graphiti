"""Graph 检索引擎 — QueryService 薄适配器 (spec FR-005 / FR-011)。

复用 infra.query.QueryService.execute_async（DSL: .entity / .topo），
不直连 Neo4j，不新建接口（Constitution IV）。

FR-011 数据隔离：对返回 rows 做防御性后过滤，剔除候选态/失效态：
  - is_candidate=True 或 valid=False 的行不返回给业务层
（图谱源层已过滤，此处为纵深防御；row 无该字段时视为有效）
"""

import logging
from typing import Any, Dict, List, Optional

from odap.infra.query.service import get_query_service

logger = logging.getLogger("semantic_retrieval.graph_engine")


class GraphEngine:
    """图检索适配器：自然语言/关键词 → QueryService DSL → 结构化结果。"""

    def __init__(self, query_service=None):
        self._qs = query_service or get_query_service()

    async def search(
        self,
        workspace_id: str,
        query: str,
        limit: int = 20,
    ) -> Dict[str, Any]:
        """关键词/实体名检索：返回匹配实体列表。

        Returns:
            {"rows": [...], "total": int, "explain": {...}}
        """
        dsl = f".entity search:{query}"
        result = await self._qs.execute_async(workspace_id, dsl, limit=limit)
        rows = self._filter_valid(result.rows)
        return {
            "rows": rows,
            "total": len(rows),
            "explain": {"source": "graph", "dsl": dsl, **(result.explain or {})},
        }

    async def neighbors(
        self,
        workspace_id: str,
        entity_id: str,
        depth: int = 1,
        direction: str = "both",
    ) -> Dict[str, Any]:
        """邻接关系检索：返回指定实体的邻居与关系。"""
        dsl = f".topo neighbors id:{entity_id} direction:{direction} depth:{depth}"
        result = await self._qs.execute_async(workspace_id, dsl, limit=100)
        rows = self._filter_valid(result.rows)
        return {
            "rows": rows,
            "total": len(rows),
            "explain": {"source": "graph", "dsl": dsl},
        }

    @staticmethod
    def _filter_valid(rows: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """FR-011 纵深防御：剔除候选态 / 失效态行。"""

        def _keep(row: Dict[str, Any]) -> bool:
            if row.get("is_candidate") is True:
                return False
            if row.get("valid") is False:
                return False
            return True

        return [r for r in rows if _keep(r)]
