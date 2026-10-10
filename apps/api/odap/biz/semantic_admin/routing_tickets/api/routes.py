"""路由工单 API（ADR-090 D-D14）——/api/semantic-admin/routing-tickets。

7 端点：
  GET  /                      列表（status/priority/assignee/engine/page）
  GET  /stats                 聚合（by_status/by_priority/breached_count）
  GET  /{id}                  详情（含 sla_breached）
  GET  /{id}/events           事件时间线
  POST /{id}/assign           指派（+可选改优先级）
  POST /{id}/transition       状态流转（状态机校验）
  POST /{id}/comment          评论（仅留痕）

规则 3：except HTTPException: raise 透传；规则 6：只调 service。
"""
from __future__ import annotations

import logging
from typing import Any, Dict, Optional

from fastapi import APIRouter, Body, Depends, HTTPException, Query

from odap.biz.semantic_admin.usl_manager.api.routes import verify_semantic_writer
from odap.infra.security.jwt_auth import get_current_user
from ..services.ticket_service import TicketService

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/semantic-admin/routing-tickets",
                   tags=["semantic-admin-routing-tickets"])

_svc_override: Optional[TicketService] = None
_svc_singleton: Optional[TicketService] = None

# 错误码 → HTTP 状态码（规则 14 失败显式）
_CODE_MAP = {
    "TICKET_NOT_FOUND_404": 404,
    "INVALID_TICKET_TRANSITION": 409,
    "INVALID_STATUS": 400,
    "INVALID_PRIORITY": 400,
    "ASSIGNEE_REQUIRED": 400,
    "NOTE_REQUIRED": 400,
    "TICKET_TERMINAL": 409,
}


def _svc() -> TicketService:
    global _svc_singleton
    if _svc_override is not None:
        return _svc_override
    if _svc_singleton is None:
        _svc_singleton = TicketService()
    return _svc_singleton


def _raise_for(r: Dict[str, Any]) -> None:
    if r.get("status") == "error":
        raise HTTPException(
            status_code=_CODE_MAP.get(r.get("code"), 500),
            detail=r.get("message"),
        )


def _actor(user: Dict[str, Any]) -> str:
    return (user or {}).get("sub") or (user or {}).get("username") or "system"


@router.get("/")
async def list_tickets(
    status: Optional[str] = Query(None),
    priority: Optional[str] = Query(None),
    assignee: Optional[str] = Query(None),
    engine: Optional[str] = Query(None),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=200),
    _user=Depends(get_current_user),
):
    try:
        r = _svc().list(status=status, priority=priority, assignee=assignee,
                        engine=engine, page=page, page_size=page_size)
        _raise_for(r)
        return r
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/stats")
async def ticket_stats(_user=Depends(get_current_user)):
    try:
        r = _svc().stats()
        _raise_for(r)
        return r
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/{ticket_id}")
async def get_ticket(ticket_id: str, _user=Depends(get_current_user)):
    try:
        r = _svc().get(ticket_id)
        _raise_for(r)
        return r["ticket"]
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/{ticket_id}/events")
async def ticket_events(ticket_id: str, _user=Depends(get_current_user)):
    try:
        r = _svc().events(ticket_id)
        _raise_for(r)
        return r
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/{ticket_id}/assign")
async def assign_ticket(ticket_id: str, body: Dict[str, Any] = Body(...),
                        user=Depends(verify_semantic_writer)):
    try:
        r = _svc().assign(ticket_id, actor=_actor(user),
                          assignee=body.get("assignee"),
                          priority=body.get("priority"))
        _raise_for(r)
        return r
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/{ticket_id}/transition")
async def transition_ticket(ticket_id: str, body: Dict[str, Any] = Body(...),
                            user=Depends(verify_semantic_writer)):
    try:
        r = _svc().transition(ticket_id, to_status=body.get("to_status"),
                              actor=_actor(user), note=body.get("note"))
        _raise_for(r)
        return r
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/{ticket_id}/comment")
async def comment_ticket(ticket_id: str, body: Dict[str, Any] = Body(...),
                         user=Depends(verify_semantic_writer)):
    try:
        r = _svc().comment(ticket_id, note=body.get("note"), actor=_actor(user))
        _raise_for(r)
        return r
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


__all__ = ["router"]
