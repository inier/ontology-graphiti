import logging
from fastapi import APIRouter, HTTPException, Query, Depends
from odap.infra.security.jwt_auth import get_current_user
from typing import Optional

from .schemas import (
    CreateSemanticMapRequest,
    SemanticMapResponse,
    SemanticMapListResponse,
    SemanticMapGraphResponse,
)
from ..services.semantic_map_service import SemanticMapService
from ..storage import Storage
from ..impl.semantic_map_generator import SemanticMapGenerator

logger = logging.getLogger("semantic_map_routes")

router = APIRouter(prefix="/api/semantic-map", tags=["semantic-map"])


def _build_service() -> SemanticMapService:
    storage = Storage()
    generator = SemanticMapGenerator()

    try:
        from odap.biz.core.ontology.design.storage.sqlite_ingest_storage import SQLiteIngestStorage
        ingest_storage = SQLiteIngestStorage()
        generator._ingest_storage = ingest_storage
    except Exception as e:
        logger.warning(f"注入 IngestStorage 失败: {e}")

    try:
        from odap.biz.core.ontology.oms.storage.sqlite_oms_storage import SQLiteOMSStorage
        oms_storage = SQLiteOMSStorage()
        generator._oms_storage = oms_storage
    except Exception as e:
        logger.warning(f"注入 OMSStorage 失败: {e}")

    return SemanticMapService(storage=storage, generator=generator)


service = _build_service()


@router.post("", response_model=SemanticMapResponse)
async def create_semantic_map(request: CreateSemanticMapRequest):
    try:
        result = service.create_semantic_map(
            name=request.name,
            description=request.description,
            ontology_version_id=request.ontology_version_id,
            ontology_id=request.ontology_id,
            scenario_id=request.scenario_id,
            created_by=request.created_by,
            generation_config=request.generation_config,
        )
        if result.get("status") == "error":
            raise HTTPException(status_code=400, detail=result.get("message"))
        return result
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("", response_model=SemanticMapListResponse)
async def list_semantic_maps(
    ontology_version_id: Optional[str] = Query(None),
    ontology_id: Optional[str] = Query(None),
    scenario_id: Optional[str] = Query(None),
    limit: int = Query(100, ge=1, le=500),
):
    try:
        return service.list_semantic_maps(
            ontology_version_id=ontology_version_id,
            ontology_id=ontology_id,
            scenario_id=scenario_id,
            limit=limit,
        )
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/{map_id}", response_model=SemanticMapResponse)
async def get_semantic_map(map_id: str,
    user=Depends(get_current_user)):
    try:
        result = service.get_semantic_map(map_id)
        if result.get("status") == "error":
            raise HTTPException(status_code=404, detail=result.get("message"))
        return result
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/{map_id}/graph", response_model=SemanticMapGraphResponse)
async def get_semantic_map_graph(map_id: str,
    user=Depends(get_current_user)):
    try:
        result = service.get_map_graph(map_id)
        if result.get("status") == "error":
            raise HTTPException(status_code=404, detail=result.get("message"))
        return result
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/{map_id}/regenerate", response_model=SemanticMapResponse)
async def regenerate_semantic_map(map_id: str,
    user=Depends(get_current_user)):
    try:
        result = service.regenerate(map_id)
        if result.get("status") == "error":
            raise HTTPException(status_code=404, detail=result.get("message"))
        return result
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.delete("/{map_id}")
async def delete_semantic_map(map_id: str,
    user=Depends(get_current_user)):
    try:
        result = service.delete_semantic_map(map_id)
        if result.get("status") == "error":
            raise HTTPException(status_code=404, detail=result.get("message"))
        return result
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
