import logging
from typing import Any, Dict, Optional

from fastapi import APIRouter, HTTPException, Query
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
