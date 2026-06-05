from fastapi import APIRouter, HTTPException, Depends
from odap.infra.security.jwt_auth import get_current_user
from pydantic import BaseModel
from typing import Any, Dict

from ..engine.impl.version_manager_impl import VersionManagerImpl


import logging

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/ontology/versions", tags=["ontology-versions"])

_version_manager = VersionManagerImpl()


class _VersionService:
    def __init__(self, manager: VersionManagerImpl):
        self._manager = manager

    def list_versions(self, document_id: str, page: int = 1, page_size: int = 20) -> Dict[str, Any]:
        try:
            results = self._manager.list_versions(document_id, page, page_size)
            return {"versions": results, "page": page, "page_size": page_size, "total": len(results)}
        except HTTPException:
            raise
        except Exception as e:
            logger.warning("silent except caught in {exc} (line 23)", exc_info=True)
            return {"status": "error", "message": str(e)}

    def create_version(self, document_id: str, changelog: str) -> Dict[str, Any]:
        try:
            result = self._manager.create_version(document_id, changelog)
            return result
        except HTTPException:
            raise
        except Exception as e:
            logger.warning("silent except caught in {exc} (line 32)", exc_info=True)
            return {"status": "error", "message": str(e)}

    def rollback_version(self, document_id: str, version_id: str) -> Dict[str, Any]:
        try:
            result = self._manager.rollback_version(document_id, version_id)
            return result
        except HTTPException:
            raise
        except Exception as e:
            logger.warning("silent except caught in {exc} (line 41)", exc_info=True)
            return {"status": "error", "message": str(e)}

    def compare_versions(self, document_id: str, version_a: str, version_b: str) -> Dict[str, Any]:
        try:
            result = self._manager.compare_versions(document_id, version_a, version_b)
            return result
        except HTTPException:
            raise
        except Exception as e:
            logger.warning("silent except caught in {exc} (line 50)", exc_info=True)
            return {"status": "error", "message": str(e)}

    def temporal_query(self, document_id: str, timestamp: str) -> Dict[str, Any]:
        try:
            result = self._manager.query_at_time(document_id, timestamp)
            if not result:
                return {"status": "error", "message": "No version found at specified time"}
            return result
        except HTTPException:
            raise
        except Exception as e:
            logger.warning("silent except caught in {exc} (line 61)", exc_info=True)
            return {"status": "error", "message": str(e)}


_version_service = _VersionService(_version_manager)


class CreateVersionRequest(BaseModel):
    changelog: str = ""


class RollbackVersionRequest(BaseModel):
    version_id: str


class TemporalQueryRequest(BaseModel):
    timestamp: str


@router.get("/{document_id}")
async def list_versions(document_id: str, page: int = 1, page_size: int = 20,
    user=Depends(get_current_user)):
    try:
        result = _version_service.list_versions(document_id, page, page_size)
        if result.get("status") == "error":
            raise HTTPException(status_code=500, detail=result.get("message", ""))
        return result
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/{document_id}")
async def create_version(document_id: str, request: CreateVersionRequest,
    user=Depends(get_current_user)):
    try:
        result = _version_service.create_version(document_id, request.changelog)
        if result.get("status") == "error":
            raise HTTPException(status_code=500, detail=result.get("message", ""))
        return result
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/{document_id}/rollback")
async def rollback_version(document_id: str, request: RollbackVersionRequest,
    user=Depends(get_current_user)):
    try:
        result = _version_service.rollback_version(document_id, request.version_id)
        if result.get("status") == "error":
            raise HTTPException(status_code=400, detail=result.get("message", ""))
        return result
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/{document_id}/compare")
async def compare_versions(document_id: str, version_a: str, version_b: str,
    user=Depends(get_current_user)):
    try:
        result = _version_service.compare_versions(document_id, version_a, version_b)
        if result.get("status") == "error":
            raise HTTPException(status_code=404, detail=result.get("message", ""))
        return result
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/{document_id}/temporal")
async def temporal_query(document_id: str, request: TemporalQueryRequest,
    user=Depends(get_current_user)):
    try:
        result = _version_service.temporal_query(document_id, request.timestamp)
        if result.get("status") == "error":
            raise HTTPException(status_code=404, detail=result.get("message", ""))
        return result
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
