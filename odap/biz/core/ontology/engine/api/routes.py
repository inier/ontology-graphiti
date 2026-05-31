from fastapi import APIRouter, HTTPException

from ..services.engine_service import EngineService
from .schemas import CreateVersionRequest, RollbackRequest, ValidateRequest, RecordAuditRequest

router = APIRouter(prefix="/api/ontology/engine", tags=["ontology-engine"])

engine_service = EngineService()


@router.post("/versions")
async def create_version(request: CreateVersionRequest):
    try:
        result = engine_service.create_version(
            request.ontology_id, request.changelog, request.valid_time, request.snapshot
        )
        return result
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/versions")
async def list_versions(ontology_id: str, page: int = 1, page_size: int = 20):
    try:
        return engine_service.list_versions(ontology_id, page, page_size)
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/versions/{version_id}")
async def get_version(version_id: str, ontology_id: str):
    try:
        result = engine_service.get_version(ontology_id, version_id)
        if result.get("status") == "error":
            raise HTTPException(status_code=404, detail=result.get("message", ""))
        return result
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/versions/{version_id}/rollback")
async def rollback_version(version_id: str, request: RollbackRequest):
    try:
        result = engine_service.rollback_version(request.target_version_id if not version_id else version_id, request.target_version_id)
        if result.get("status") == "error":
            raise HTTPException(status_code=400, detail=result.get("message", ""))
        return result
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/versions/compare")
async def compare_versions(ontology_id: str, v1_id: str, v2_id: str):
    try:
        return engine_service.compare_versions(ontology_id, v1_id, v2_id)
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/versions/temporal-query")
async def temporal_query(ontology_id: str, timestamp: str):
    try:
        result = engine_service.query_at_time(ontology_id, timestamp)
        if result.get("status") == "error":
            raise HTTPException(status_code=404, detail=result.get("message", ""))
        return result
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/validate")
async def validate(request: ValidateRequest):
    try:
        return engine_service.validate(request.type_def, request.properties)
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/audit")
async def list_audits(entity_type_id: str = None, page: int = 1, page_size: int = 20):
    try:
        return engine_service.list_audits(entity_type_id, page, page_size)
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/audit/{audit_id}")
async def get_audit(audit_id: str):
    try:
        result = engine_service.get_audit(audit_id)
        if result.get("status") == "error":
            raise HTTPException(status_code=404, detail=result.get("message", ""))
        return result
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/audit")
async def record_audit(request: RecordAuditRequest):
    try:
        return engine_service.record_audit(
            request.entity_type_id, request.source,
            request.process_steps, request.transform_rules, request.result
        )
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
