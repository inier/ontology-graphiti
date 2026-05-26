import logging
from typing import Any, Dict, Optional

from fastapi import APIRouter, HTTPException, Query

from .protocols import QueryResult
from .service import QueryService

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/query", tags=["query"])


def _get_query_service() -> QueryService:
    return QueryService()


@router.post("/execute", response_model=QueryResult)
def execute_query(
    query: str = Query(..., description="查询表达式，如 .entity with(type='MilitaryUnit')"),
    workspace_id: str = Query("default", description="工作空间ID"),
    limit: int = Query(20, ge=1, le=100, description="返回数量限制"),
) -> QueryResult:
    """
    执行统一查询

    支持四种查询源：
    - .schema with(type='Unit')  -- 查询本体类型定义
    - .entity with(type='MilitaryUnit')  -- 查询运行时实体
    - .topo neighbors(id='xxx', depth=2)  -- 查询拓扑关系
    - .temporal at('2025-01-01')  -- 查询时态数据
    """
    service = _get_query_service()
    try:
        return service.execute(workspace_id=workspace_id, query=query, limit=limit)
    except Exception as e:
        logger.error(f"Query execution error: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/explain")
def explain_query(
    query: str = Query(..., description="查询表达式"),
    workspace_id: str = Query("default", description="工作空间ID"),
) -> Dict[str, Any]:
    """
    解释查询表达式（不执行，仅返回解析结果）
    """
    service = _get_query_service()
    return service.explain(workspace_id=workspace_id, query=query)


@router.get("/sources")
def list_sources() -> Dict[str, Any]:
    """
    列出可用的查询源
    """
    return {
        "sources": [
            {
                "name": "schema",
                "prefix": ".schema",
                "description": "查询本体类型定义（实体类型、关系类型、动作类型）",
                "examples": [
                    ".schema with(type='Unit')",
                    ".schema with(kind='link_definitions')",
                    ".schema with(kind='action_types')",
                ],
            },
            {
                "name": "entity",
                "prefix": ".entity",
                "description": "查询运行时实体",
                "examples": [
                    ".entity with(type='MilitaryUnit')",
                    ".entity with(search='装甲部队')",
                    ".entity with(id='entity-mil-abc123')",
                ],
            },
            {
                "name": "topo",
                "prefix": ".topo",
                "description": "查询拓扑关系和图遍历",
                "examples": [
                    ".topo neighbors(id='entity-mil-abc123', depth=2)",
                    ".topo relations(id='entity-mil-abc123', type='located_at')",
                    ".topo path(from='id1', to='id2', max_hops=5)",
                ],
            },
            {
                "name": "temporal",
                "prefix": ".temporal",
                "description": "查询时态数据（历史版本、双时态查询）",
                "examples": [
                    ".temporal at('2025-01-01')",
                    ".temporal history(id='entity-mil-abc123')",
                ],
            },
        ]
    }
