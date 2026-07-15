from fastapi import APIRouter, HTTPException, Query, Depends
from odap.infra.security.jwt_auth import get_current_user
from odap.web.api.response_models import DictResponse
from typing import Optional

from .service_catalog import ServiceCatalogService

router = APIRouter(prefix="/api/ontology/servitization/catalog", tags=["service-catalog"])
service = ServiceCatalogService.get_instance()


@router.post("/register", response_model=DictResponse)
async def register_service(request: dict,
    user=Depends(get_current_user)):
    try:
        result = service.register_service(**request)
        if result.get("status") == "error":
            raise HTTPException(status_code=400, detail=result["message"])
        return result
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/{catalog_id}", response_model=DictResponse)
async def get_entry(catalog_id: str,
    user=Depends(get_current_user)):
    result = service.get_entry(catalog_id)
    if result.get("status") == "error":
        raise HTTPException(status_code=404, detail=result["message"])
    return result


@router.get("", response_model=DictResponse)
async def list_services(
    service_type: Optional[str] = Query(None),
    source_ontology_id: Optional[str] = Query(None),
    status: Optional[str] = Query(None),
    source_object_type: Optional[str] = Query(None),
    limit: int = Query(100),
):
    return service.list_services(service_type, source_ontology_id, status,
                                 source_object_type, limit)


@router.get("/discover/search", response_model=DictResponse)
async def discover_services(
    capability: Optional[str] = Query(None),
    object_type: Optional[str] = Query(None),
    scenario_id: Optional[str] = Query(None),
    user=Depends(get_current_user)):
    return service.discover_services(capability, object_type, scenario_id)


@router.post("/{catalog_id}/deprecate", response_model=DictResponse)
async def deprecate_service(catalog_id: str,
    user=Depends(get_current_user)):
    result = service.deprecate_service(catalog_id)
    if result.get("status") == "error":
        raise HTTPException(status_code=404, detail=result["message"])
    return result


@router.post("/{catalog_id}/retire", response_model=DictResponse)
async def retire_service(catalog_id: str,
    user=Depends(get_current_user)):
    result = service.retire_service(catalog_id)
    if result.get("status") == "error":
        raise HTTPException(status_code=404, detail=result["message"])
    return result


@router.delete("/{catalog_id}", response_model=DictResponse)
async def delete_entry(catalog_id: str,
    user=Depends(get_current_user)):
    result = service.delete_entry(catalog_id)
    if result.get("status") == "error":
        raise HTTPException(status_code=404, detail=result["message"])
    return result


@router.post("/on-version-change", response_model=DictResponse)
async def on_ontology_version_changed(request: dict,
    user=Depends(get_current_user)):
    try:
        return service.on_ontology_version_changed(
            request.get("ontology_id", ""), request.get("new_version_id", ""))
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/{catalog_id}/versions", response_model=DictResponse)
async def get_version_links(catalog_id: str,
    user=Depends(get_current_user)):
    return service.get_version_links(catalog_id)


@router.get("/{catalog_id}/health", response_model=DictResponse)
async def health_check(catalog_id: str,
    user=Depends(get_current_user)):
    result = service.health_check(catalog_id)
    if result.get("status") == "error":
        raise HTTPException(status_code=404, detail=result["message"])
    return result
