"""
NLQueryRoutes — 自然语言统一查询入口。

POST /api/ontology/query/nl
  Body: { query: str, workspace_id?, ontology_id?, limit?, force_intent? }
  返回：{ status, intent, query, source?, rows, total, ... }
"""
import logging
from typing import Any, Dict, Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from typing import List

from odap.infra.security.jwt_auth import get_current_user

from .nl_dispatcher import NLDispatcher

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/ontology/query", tags=["ontology-nl-query"])


class NLQueryRequest(BaseModel):
    query: str = Field(..., description="自然语言查询文本")
    workspace_id: str = Field(default="default", description="工作空间 ID")
    ontology_id: Optional[str] = Field(default=None, description="本体 ID")
    limit: int = Field(default=20, ge=1, le=100, description="结果上限")
    force_intent: Optional[str] = Field(
        default=None,
        description="强制 intent: structured | unstructured | hybrid | action",
    )


class NLQueryResponse(BaseModel):
    status: str
    intent: str
    query: str
    source: Optional[str] = None
    rows: List[Dict[str, Any]] = Field(default_factory=list)
    total: int = 0
    translated_dsl: Optional[str] = None
    structured_count: Optional[int] = None
    unstructured_count: Optional[int] = None
    skill_name: Optional[str] = None
    error: Optional[str] = None
    message: Optional[str] = None


@router.post("/nl", response_model=NLQueryResponse)
async def nl_query(request: NLQueryRequest, user=Depends(get_current_user)) -> NLQueryResponse:
    """统一 NL 查询入口（结构化 + 非结构化 + Hybrid + Action）。"""
    _validate_query(request)
    dispatcher = _get_dispatcher()
    result = await _do_dispatch(dispatcher, request)
    return _build_response(result, request)


def _validate_query(request: NLQueryRequest) -> None:
    if not request.query or not request.query.strip():
        raise HTTPException(status_code=400, detail="query is required")


def _get_dispatcher() -> NLDispatcher:
    try:
        return NLDispatcher.get_instance()
    except Exception as e:
        logger.error("NLDispatcher init failed: %s", e)
        raise HTTPException(status_code=503, detail=f"dispatcher unavailable: {e}")


async def _do_dispatch(dispatcher: NLDispatcher, request: NLQueryRequest) -> Dict[str, Any]:
    hints: Dict[str, Any] = {}
    if request.force_intent:
        hints["force_intent"] = request.force_intent
    try:
        return await dispatcher.dispatch(
            query=request.query,
            workspace_id=request.workspace_id,
            ontology_id=request.ontology_id,
            limit=request.limit,
            hints=hints,
        )
    except HTTPException:
        raise
    except Exception as e:
        logger.error("NL dispatch error: %s", e)
        raise HTTPException(status_code=500, detail=str(e))


def _build_response(result: Dict[str, Any], request: NLQueryRequest) -> NLQueryResponse:
    return NLQueryResponse(
        status=result.get("status", "error"),
        intent=result.get("intent", "unknown"),
        query=result.get("query", request.query),
        source=result.get("source"),
        rows=result.get("rows", []),
        total=result.get("total", 0),
        translated_dsl=result.get("translated_dsl"),
        structured_count=result.get("structured_count"),
        unstructured_count=result.get("unstructured_count"),
        skill_name=result.get("skill_name"),
        error=result.get("error"),
        message=result.get("message"),
    )


__all__ = ["router"]
