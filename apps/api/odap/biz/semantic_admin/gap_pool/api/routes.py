"""gap_pool 路由（规则 3：except HTTPException: raise 透传；规则 6：只调 service）。"""
from __future__ import annotations

import logging
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query

from odap.infra.security.jwt_auth import get_current_user
from odap.biz.semantic_admin.usl_manager.api.routes import verify_semantic_writer
from ..services.gap_service import GapService
from .schemas import DismissRequest, PromoteRequest

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/semantic-admin/gaps", tags=["semantic-admin-gaps"])

_gap_service_override: Optional[GapService] = None
_gap_service_singleton: Optional[GapService] = None


def _svc() -> GapService:
    global _gap_service_singleton
    if _gap_service_override is not None:
        return _gap_service_override
    if _gap_service_singleton is None:
        _gap_service_singleton = GapService()
    return _gap_service_singleton


@router.get("/")
async def list_gaps(
    status: Optional[str] = Query(None),
    source: Optional[str] = Query(None),
    workspace_id: Optional[str] = Query(None),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=200),
    _user=Depends(get_current_user),
):
    try:
        r = _svc().list_gaps(status=status, source=source,
                             workspace_id=workspace_id, page=page, page_size=page_size)
        if r.get("status") == "error":
            raise HTTPException(status_code=500, detail=r["message"])
        return r
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/stats")
async def gap_stats(_user=Depends(get_current_user)):
    try:
        r = _svc().stats()
        if r.get("status") == "error":
            raise HTTPException(status_code=500, detail=r["message"])
        return r
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/{gap_id}")
async def get_gap(gap_id: str, _user=Depends(get_current_user)):
    try:
        r = _svc().get_gap(gap_id)
        if r.get("status") == "error":
            code = 404 if r.get("code") == "GAP_NOT_FOUND_404" else 500
            raise HTTPException(status_code=code, detail=r["message"])
        return r["gap"]
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/{gap_id}/promote")
async def promote_gap(gap_id: str, body: PromoteRequest = PromoteRequest(),
                      user=Depends(verify_semantic_writer)):
    try:
        actor = (user or {}).get("sub") or (user or {}).get("username") or "system"
        r = _svc().promote(gap_id, actor=actor,
                           domain_id=body.domain_id, workspace_id=body.workspace_id)
        if r.get("status") == "error":
            code = 404 if r.get("code") == "GAP_NOT_FOUND_404" else 500
            raise HTTPException(status_code=code, detail=r["message"])
        return r
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/{gap_id}/dismiss")
async def dismiss_gap(gap_id: str, body: DismissRequest,
                      user=Depends(verify_semantic_writer)):
    try:
        actor = (user or {}).get("sub") or (user or {}).get("username") or "system"
        r = _svc().dismiss(gap_id, reason=body.reason, actor=actor)
        if r.get("status") == "error":
            code = 404 if r.get("code") == "GAP_NOT_FOUND_404" else 500
            raise HTTPException(status_code=code, detail=r["message"])
        return r
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/{gap_id}/resolve-check")
async def resolve_check(gap_id: str, _user=Depends(get_current_user)):
    try:
        r = _svc().resolve_check(gap_id)
        if r.get("status") == "error":
            code = 404 if r.get("code") == "GAP_NOT_FOUND_404" else 500
            raise HTTPException(status_code=code, detail=r["message"])
        return r
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
