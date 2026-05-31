from fastapi import APIRouter, HTTPException

from ..services.model_service import ModelService
from .schemas import (
    BatchImportRequest,
    CreateDocumentRequest,
    CreateEntityTypeRequest,
    CreateInstanceRequest,
    UpdateEntityTypeRequest,
    UpdateInstanceRequest,
)

router = APIRouter(prefix="/api/ontology/model", tags=["ontology-model"])

model_service = ModelService()


@router.post("/entity-types")
async def create_entity_type(request: CreateEntityTypeRequest):
    try:
        result = model_service.create_entity_type(request.model_dump())
        if result.get("status") == "error":
            raise HTTPException(status_code=400, detail=result.get("message", ""))
        return result
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/entity-types")
async def list_entity_types(page: int = 1, page_size: int = 20, name: str = None, classification_level: str = None):
    try:
        filters = {}
        if name:
            filters["name"] = name
        if classification_level:
            filters["classification_level"] = classification_level
        return model_service.list_entity_types(filters or None, page, page_size)
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/entity-types/{type_id}")
async def get_entity_type(type_id: str):
    try:
        result = model_service.get_entity_type(type_id)
        if result.get("status") == "error":
            raise HTTPException(status_code=404, detail=result.get("message", ""))
        return result
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.put("/entity-types/{type_id}")
async def update_entity_type(type_id: str, request: UpdateEntityTypeRequest):
    try:
        data = request.model_dump(exclude_none=True)
        result = model_service.update_entity_type(type_id, data)
        if result.get("status") == "error":
            raise HTTPException(status_code=404, detail=result.get("message", ""))
        return result
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.delete("/entity-types/{type_id}")
async def delete_entity_type(type_id: str):
    try:
        result = model_service.delete_entity_type(type_id)
        if result.get("status") == "error":
            raise HTTPException(status_code=404, detail=result.get("message", ""))
        return result
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/instances")
async def create_instance(request: CreateInstanceRequest):
    try:
        data = request.model_dump()
        result = model_service.create_instance(data)
        if result.get("status") == "error":
            raise HTTPException(status_code=400, detail=result.get("message", ""))
        return result
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/instances")
async def list_instances(type_id: str = None, workspace_id: str = None, page: int = 1, page_size: int = 20):
    try:
        return model_service.list_instances(type_id, workspace_id, page, page_size)
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/instances/{instance_id}")
async def get_instance(instance_id: str):
    try:
        result = model_service.get_instance(instance_id)
        if result.get("status") == "error":
            raise HTTPException(status_code=404, detail=result.get("message", ""))
        return result
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.put("/instances/{instance_id}")
async def update_instance(instance_id: str, request: UpdateInstanceRequest):
    try:
        data = request.model_dump(exclude_none=True)
        result = model_service.update_instance(instance_id, data)
        if result.get("status") == "error":
            raise HTTPException(status_code=404, detail=result.get("message", ""))
        return result
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.delete("/instances/{instance_id}")
async def delete_instance(instance_id: str):
    try:
        result = model_service.delete_instance(instance_id)
        if result.get("status") == "error":
            raise HTTPException(status_code=404, detail=result.get("message", ""))
        return result
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/instances/batch")
async def batch_import(request: BatchImportRequest):
    try:
        return model_service.batch_import(request.instances)
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/documents/{ontology_id}")
async def get_document(ontology_id: str):
    try:
        result = model_service.get_document(ontology_id)
        if result.get("status") == "error":
            raise HTTPException(status_code=404, detail=result.get("message", ""))
        return result
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/documents")
async def create_document(request: CreateDocumentRequest):
    try:
        data = request.model_dump()
        result = model_service.create_document(data)
        if result.get("status") == "error":
            raise HTTPException(status_code=400, detail=result.get("message", ""))
        return result
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/documents/{ontology_id}/export")
async def export_document(ontology_id: str):
    try:
        result = model_service.export_document(ontology_id)
        if result.get("status") == "error":
            raise HTTPException(status_code=404, detail=result.get("message", ""))
        return result
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
