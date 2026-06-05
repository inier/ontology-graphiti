from fastapi import APIRouter, HTTPException, Depends
from odap.infra.security.jwt_auth import get_current_user
from typing import Optional

from .schemas import (
    ObjectQuery, ObjectQueryResponse,
    SemanticQuery, SemanticQueryResponse,
)
from .object_service import get_object_service

router = APIRouter(prefix="/api/objects", tags=["object-service"])


@router.post("/query", response_model=ObjectQueryResponse)
async def query_objects(query: ObjectQuery,
    user=Depends(get_current_user)):
    service = get_object_service()
    return await service.query_objects(query)


@router.post("/semantic", response_model=SemanticQueryResponse)
async def semantic_query(query: SemanticQuery,
    user=Depends(get_current_user)):
    service = get_object_service()
    return await service.semantic_query(query)


@router.get("/{object_id}")
async def get_object(object_id: str, object_type: Optional[str] = None,
    user=Depends(get_current_user)):
    service = get_object_service()
    result = await service.get_object(object_id, object_type)
    if not result:
        raise HTTPException(status_code=404, detail="对象不存在")
    return result
