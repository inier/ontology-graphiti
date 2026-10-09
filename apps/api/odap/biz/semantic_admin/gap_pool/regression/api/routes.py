"""gap-regression 路由（规则 3：except HTTPException: raise 透传；规则 6：只调 service）。

ADR-088 D7：6 端点，prefix /api/semantic-admin/gap-regression，全 get_current_user。
resolve_check（fast 语义）不动——paired 是贵重操作，走独立端点防误调。
"""
from __future__ import annotations

import logging
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel

from odap.infra.security.jwt_auth import get_current_user
from ...regression.service import RegressionService

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/semantic-admin/gap-regression",
                   tags=["semantic-admin-gap-regression"])

_reg_service_override: Optional[RegressionService] = None
_reg_service_singleton: Optional[RegressionService] = None


def _svc() -> RegressionService:
    global _reg_service_singleton
    if _reg_service_override is not None:
        return _reg_service_override
    if _reg_service_singleton is None:
        _reg_service_singleton = RegressionService()
    return _reg_service_singleton


class BuildSetRequest(BaseModel):
    status: Optional[str] = None
    workspace_id: Optional[str] = None
    domain_id: Optional[str] = None
    min_heat: int = 1


@router.post("/sets/build")
async def build_set(body: BuildSetRequest = BuildSetRequest(),
                    _user=Depends(get_current_user)):
    try:
        r = _svc().build(body.model_dump())
        if r.get("status") == "error":
            raise HTTPException(status_code=500, detail=r["message"])
        return r
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/sets")
async def list_sets(page: int = Query(1, ge=1),
                    page_size: int = Query(20, ge=1, le=200),
                    _user=Depends(get_current_user)):
    try:
        r = _svc().list_sets(page=page, page_size=page_size)
        if r.get("status") == "error":
            raise HTTPException(status_code=500, detail=r["message"])
        return r
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/sets/{set_id}")
async def get_set(set_id: str, _user=Depends(get_current_user)):
    try:
        r = _svc().get_set(set_id)
        if r.get("status") == "error":
            code = 404 if r.get("code") == "SET_NOT_FOUND_404" else 500
            raise HTTPException(status_code=code, detail=r["message"])
        return r["set"]
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/sets/{set_id}/replay")
async def replay_set(set_id: str, _user=Depends(get_current_user)):
    try:
        r = await _svc().replay(set_id)
        if r.get("status") == "error":
            code = 404 if r.get("code") == "SET_NOT_FOUND_404" else 500
            raise HTTPException(status_code=code, detail=r["message"])
        return r
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/reports")
async def list_reports(set_id: Optional[str] = Query(None),
                       page: int = Query(1, ge=1),
                       page_size: int = Query(20, ge=1, le=200),
                       _user=Depends(get_current_user)):
    try:
        r = _svc().list_reports(set_id=set_id, page=page, page_size=page_size)
        if r.get("status") == "error":
            raise HTTPException(status_code=500, detail=r["message"])
        return r
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
        return r["report"]
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
