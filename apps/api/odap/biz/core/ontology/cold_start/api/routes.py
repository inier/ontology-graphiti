"""
冷启动 API 路由

GET  /api/ontology/cold-start/industries  - 列出可用行业
POST /api/ontology/cold-start/bootstrap   - 触发冷启动引导
"""
from __future__ import annotations

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from ..services import ColdStartService


router = APIRouter(prefix="/api/ontology/cold-start", tags=["cold-start"])
cold_start_service = ColdStartService()


class BootstrapRequest(BaseModel):
    workspace_id: str
    industry: str = Field(..., description="finance / healthcare / manufacturing")


@router.get("/industries")
async def list_industries():
    """列出可用行业模板"""
    try:
        return cold_start_service.list_available_industries()
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/bootstrap")
async def bootstrap_workspace(request: BootstrapRequest):
    """触发工作空间冷启动引导"""
    try:
        return cold_start_service.bootstrap_workspace(request.workspace_id, request.industry)
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
