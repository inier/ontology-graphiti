from fastapi import APIRouter, HTTPException, Query
from typing import Optional

from .schemas import (
    CreateTemplateRequest, GenerateServiceRequest,
    DeployServiceRequest, GenerateFromOntologyRequest,
)
from ..services import get_servitization_service

router = APIRouter(prefix="/api/ontology/servitization", tags=["ontology-servitization"])


@router.post("/templates", response_model=dict)
async def create_template(request: CreateTemplateRequest):
    try:
        service = get_servitization_service()
        result = service.create_template(request.model_dump())
        if result.get("status") == "error":
            raise HTTPException(status_code=400, detail=result["message"])
        return result
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/templates", response_model=dict)
async def list_templates(service_type: Optional[str] = Query(None)):
    try:
        service = get_servitization_service()
        return service.list_templates(service_type=service_type)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/services/generate", response_model=dict)
async def generate_service(request: GenerateServiceRequest):
    try:
        service = get_servitization_service()
        overrides = request.model_dump(exclude={"template_id"})
        result = service.generate_service(request.template_id, overrides)
        if result.get("status") == "error":
            raise HTTPException(status_code=400, detail=result["message"])
        return result
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/services", response_model=dict)
async def list_services(
    service_type: Optional[str] = Query(None),
    status: Optional[str] = Query(None),
):
    try:
        service = get_servitization_service()
        return service.list_services(service_type=service_type, status=status)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/services/{service_id}", response_model=dict)
async def get_service(service_id: str):
    try:
        service = get_servitization_service()
        result = service.get_service(service_id)
        if result.get("status") == "error":
            raise HTTPException(status_code=404, detail=result["message"])
        return result
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/services/{service_id}/deploy", response_model=dict)
async def deploy_service(service_id: str):
    try:
        service = get_servitization_service()
        result = service.deploy_service(service_id)
        if result.get("status") == "error":
            raise HTTPException(status_code=400, detail=result["message"])
        return result
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/services/{service_id}/undeploy", response_model=dict)
async def undeploy_service(service_id: str):
    try:
        service = get_servitization_service()
        result = service.undeploy_service(service_id)
        if result.get("status") == "error":
            raise HTTPException(status_code=400, detail=result["message"])
        return result
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/generate-from-ontology", response_model=dict)
async def generate_from_ontology(request: GenerateFromOntologyRequest):
    try:
        service = get_servitization_service()
        result = service.generate_from_ontology(
            ontology_id=request.ontology_id,
            service_type=request.service_type.value,
        )
        if result.get("status") == "error":
            raise HTTPException(status_code=400, detail=result["message"])
        return result
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
