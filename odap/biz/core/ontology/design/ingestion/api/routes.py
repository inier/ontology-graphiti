from fastapi import APIRouter, HTTPException, UploadFile, File, Form, Depends
from odap.infra.security.jwt_auth import get_current_user
from typing import Optional

from ..services.ingest_service import IngestService
from .schemas import BatchImportRequest, ExtractRequest, TaskResponse, BatchImportResponse

router = APIRouter(prefix="/api/ontology/ingestion", tags=["ontology-ingestion"])

ingest_service = IngestService()


@router.post("/upload")
async def upload_file(
    file: UploadFile = File(..),
    workspace_id: str = Form("default"),,
    user=Depends(get_current_user)):
    try:
        file_data = await file.read()
        result = ingest_service.upload_file(
            file_name=file.filename,
            file_data=file_data,
            workspace_id=workspace_id,
            content_type=file.content_type or "application/octet-stream",
        )
        return result
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/tasks/{task_id}")
async def get_task_status(task_id: str,
    user=Depends(get_current_user)):
    try:
        result = ingest_service.get_task_status(task_id)
        if result.get("status") == "error" and "not found" in result.get("message", ""):
            raise HTTPException(status_code=404, detail=result.get("message"))
        return result
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/extract")
async def extract_entities(request: ExtractRequest,
    user=Depends(get_current_user)):
    try:
        result = ingest_service.process_file(request.task_id)
        if result.get("status") == "error":
            raise HTTPException(status_code=400, detail=result.get("message"))
        return result
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/batch", response_model=BatchImportResponse)
async def batch_import(request: BatchImportRequest,
    user=Depends(get_current_user)):
    try:
        result = ingest_service.batch_import(
            entity_type_id=request.entity_type_id,
            data=request.data,
            format=request.format,
            workspace_id=request.workspace_id,
        )
        if result.get("status") == "error":
            raise HTTPException(status_code=400, detail=result.get("message", "Batch import failed"))
        return BatchImportResponse(**result)
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
