"""drift_scan 路由（规则 3：except HTTPException: raise；规则 6：只调 service）。"""
from __future__ import annotations

import logging
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query

from odap.infra.security.jwt_auth import get_current_user
from odap.biz.semantic_admin.drift_scan.services import DriftService
from .schemas import ScanRequest

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/semantic-admin/drift", tags=["semantic-admin-drift"])

_drift_service_override: Optional[DriftService] = None
_drift_service_singleton: Optional[DriftService] = None


def _svc() -> DriftService:
    global _drift_service_singleton
    if _drift_service_override is not None:
        return _drift_service_override
    if _drift_service_singleton is None:
        _drift_service_singleton = DriftService()
    return _drift_service_singleton


@router.post("/scan")
async def trigger_scan(body: ScanRequest = ScanRequest(), _user=Depends(get_current_user)):
    try:
        scope = {k: v for k, v in {"ontology_id": body.ontology_id,
                                   "domain_id": body.domain_id}.items() if v}
        r = _svc().run_scan(scope=scope, trigger="manual", ontology_id=body.ontology_id)
        if r.get("status") == "error" and not r.get("report_id"):
            raise HTTPException(status_code=500, detail=r["message"])
        return r
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/reports")
async def list_reports(trigger: Optional[str] = Query(None),
                       status: Optional[str] = Query(None),
                       page: int = Query(1, ge=1), page_size: int = Query(20, ge=1, le=200),
                       _user=Depends(get_current_user)):
    try:
        r = _svc().list_reports(trigger=trigger, status=status, page=page, page_size=page_size)
        if r.get("status") == "error":
            raise HTTPException(status_code=500, detail=r["message"])
        return r
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/reports/latest")
async def latest_report(_user=Depends(get_current_user)):
    try:
        return _svc().latest_report()
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/reports/{report_id}")
async def get_report(report_id: str, _user=Depends(get_current_user)):
    try:
        r = _svc().get_report(report_id)
        if r.get("status") == "error":
            code = 404 if r.get("code") == "REPORT_NOT_FOUND_404" else 500
            raise HTTPException(status_code=code, detail=r["message"])
        return r
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
