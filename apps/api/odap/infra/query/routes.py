import logging
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, HTTPException, Query, Depends
from odap.infra.security.jwt_auth import get_current_user
from pydantic import BaseModel, Field

from .protocols import QueryResult
from .service import QueryService

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/query", tags=["query"])


class UnifiedQueryRequest(BaseModel):
    query: str
    workspace_id: str = "default"
    limit: int = Field(default=20, ge=1, le=100)
    agent_safe: bool = False


class ValidateQueryRequest(BaseModel):
    query: str


class EntityQueryRequest(BaseModel):
    query: Optional[Dict[str, Any]] = None
    workspace_id: Optional[str] = None


class RelationQueryRequest(BaseModel):
    query: Optional[Dict[str, Any]] = None
    workspace_id: Optional[str] = None


class ComplexQueryRequest(BaseModel):
    conditions: List[Dict[str, Any]] = Field(default_factory=list)
    workspace_id: Optional[str] = None


def _get_query_service() -> QueryService:
    return QueryService()


@router.post("")
def unified_query(request: UnifiedQueryRequest) -> QueryResult:
    service = _get_query_service()
    try:
        return service.execute(
            workspace_id=request.workspace_id,
            query=request.query,
            limit=request.limit,
            agent_safe=request.agent_safe,
        )
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Query execution error: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/execute", response_model=QueryResult)
def execute_query(
    query: str = Query(..., description="Query expression"),
    workspace_id: str = Query("default", description="Workspace ID"),
    limit: int = Query(20, ge=1, le=100, description="Result limit"),
) -> QueryResult:
    service = _get_query_service()
    try:
        return service.execute(workspace_id=workspace_id, query=query, limit=limit)
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Query execution error: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/explain")
def explain_query(
    query: str = Query(..., description="Query expression"),
    workspace_id: str = Query("default", description="Workspace ID"),
) -> Dict[str, Any]:
    service = _get_query_service()
    return service.explain(workspace_id=workspace_id, query=query)


@router.get("/sources")
def list_sources() -> Dict[str, Any]:
    service = _get_query_service()
    sources = service.list_sources()
    return {"sources": sources}


@router.post("/validate")
def validate_query(request: ValidateQueryRequest) -> Dict[str, Any]:
    service = _get_query_service()
    return service.validate(request.query)


@router.post("/entities")
def query_entities(request: EntityQueryRequest):
    """结构化实体查询（前端 api.queryEntities 调用）"""
    service = _get_query_service()
    try:
        entity_source = service._entity_source
        filters = request.query or {}
        workspace_id = request.workspace_id or "default"

        # 关键词搜索
        keyword = filters.get("keyword")
        if keyword:
            results = entity_source.search_entities(query=keyword, top_k=50, workspace_id=workspace_id)
        else:
            results = entity_source.query_entities(filters=filters, workspace_id=workspace_id)

        # 统一格式
        entities = []
        for r in results:
            if isinstance(r, dict):
                entities.append({
                    "entity_id": r.get("entity_id") or r.get("id") or r.get("uuid", ""),
                    "name": r.get("name", ""),
                    "type": r.get("type") or r.get("entity_type", ""),
                    "properties": r.get("properties") or r,
                })
        return {"entities": entities, "total": len(entities)}
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Entity query error: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/relations")
def query_relations(request: RelationQueryRequest):
    """结构化关系查询（前端 api.queryRelations 调用）"""
    service = _get_query_service()
    try:
        topo_source = service._topo_source
        filters = request.query or {}
        workspace_id = request.workspace_id or "default"

        source_id = filters.get("source_id")
        relation_type = filters.get("relation_type")

        if source_id:
            results = topo_source.get_relations(entity_id=source_id, relation_type=relation_type)
        else:
            results = []

        relations = []
        for r in results:
            if isinstance(r, dict):
                relations.append(r)
        return {"relations": relations, "total": len(relations)}
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Relation query error: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/complex")
def complex_query(request: ComplexQueryRequest):
    """复合条件查询（前端 api.complexQuery 调用）"""
    service = _get_query_service()
    try:
        entity_source = service._entity_source
        workspace_id = request.workspace_id or "default"

        # 将 conditions 转为 filters
        filters = {}
        for cond in request.conditions:
            cond_type = cond.get("type", "")
            value = cond.get("value", "")
            if cond_type == "keyword":
                filters["keyword"] = value
            elif cond_type == "type":
                filters["type"] = value
            elif cond_type == "area":
                filters["area"] = value

        keyword = filters.get("keyword")
        if keyword:
            results = entity_source.search_entities(query=keyword, top_k=50, workspace_id=workspace_id)
        else:
            results = entity_source.query_entities(filters=filters, workspace_id=workspace_id)

        entities = []
        for r in results:
            if isinstance(r, dict):
                entities.append({
                    "entity_id": r.get("entity_id") or r.get("id") or r.get("uuid", ""),
                    "name": r.get("name", ""),
                    "type": r.get("type") or r.get("entity_type", ""),
                    "properties": r.get("properties") or r,
                })
        return {"results": entities, "total": len(entities)}
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Complex query error: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/history")
def query_history(limit: int = Query(50, ge=1, le=200)):
    """查询历史（前端 api.getQueryHistory 调用）"""
    return {"history": [], "limit": limit}
