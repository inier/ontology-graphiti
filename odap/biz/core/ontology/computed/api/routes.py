"""Computed Property - FastAPI 路由 (T398)

前缀: /api/ontology/computed
端点：
- POST   /properties                    创建 ComputedProperty
- GET    /properties                    列出 (query: target_type, enabled_only)
- GET    /properties/{id}               获取
- PUT    /properties/{id}               更新
- DELETE /properties/{id}               删除
- POST   /properties/{id}/evaluate      评估单实例
- POST   /properties/{id}/recompute     触发重算
- GET    /properties/{id}/jobs          任务历史
- GET    /jobs/{job_id}                 任务状态
"""
from __future__ import annotations

from typing import Optional

from fastapi import APIRouter, HTTPException, Query

from ..services import ComputedService
from .schemas import (
    CreateComputedPropertyRequest,
    EvaluateRequest,
    ListComputedPropertiesResponse,
    ListJobsResponse,
    RecomputeRequest,
    UpdateComputedPropertyRequest,
)


router = APIRouter(prefix="/api/ontology/computed", tags=["computed"])

# 模块级单例
computed_service = ComputedService()


@router.post("/properties", response_model=ListComputedPropertiesResponse)
async def create_property(request: CreateComputedPropertyRequest):
    """创建 ComputedProperty"""
    try:
        result = computed_service.create_property(request.model_dump())
        if result.get("status") == "error":
            raise HTTPException(status_code=400, detail=result["message"])
        return {"properties": [result], "count": 1}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/properties", response_model=ListComputedPropertiesResponse)
async def list_properties(
    target_type: Optional[str] = Query(None, description="按 target_type_id 过滤"),
    enabled_only: bool = Query(False, description="仅返回启用的"),
):
    """列出 ComputedProperty"""
    try:
        result = computed_service.list_properties(
            target_type=target_type, enabled_only=enabled_only
        )
        if result.get("status") == "error":
            raise HTTPException(status_code=400, detail=result["message"])
        return result
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/properties/{property_id}")
async def get_property(property_id: str):
    """获取单条 ComputedProperty"""
    try:
        result = computed_service.get_property(property_id)
        if result.get("status") == "error":
            raise HTTPException(status_code=404, detail=result["message"])
        return result
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.put("/properties/{property_id}")
async def update_property(
    property_id: str, request: UpdateComputedPropertyRequest
):
    """更新 ComputedProperty（部分字段）"""
    try:
        payload = {k: v for k, v in request.model_dump().items() if v is not None}
        result = computed_service.update_property(property_id, payload)
        if result.get("status") == "error":
            status_code = 404 if "not found" in result["message"] else 400
            raise HTTPException(status_code=status_code, detail=result["message"])
        return result
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.delete("/properties/{property_id}")
async def delete_property(property_id: str):
    """删除 ComputedProperty"""
    try:
        result = computed_service.delete_property(property_id)
        if result.get("status") == "error":
            raise HTTPException(status_code=404, detail=result["message"])
        return result
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/properties/{property_id}/evaluate")
async def evaluate_property(
    property_id: str, request: EvaluateRequest
):
    """评估单实例（不写库）"""
    try:
        result = computed_service.evaluate_property(
            prop_id=property_id,
            instance_id=request.instance_id,
            instance_data=request.instance_data,
        )
        if result.get("status") == "error":
            status_code = 404 if "not found" in result["message"] else 400
            raise HTTPException(status_code=status_code, detail=result["message"])
        return result
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/properties/{property_id}/recompute")
async def recompute_property(
    property_id: str, request: RecomputeRequest
):
    """触发重算（full / incremental）"""
    try:
        result = computed_service.trigger_recompute(
            prop_id=property_id,
            mode=request.mode,
            changed_property_id=request.changed_property_id,
        )
        if result.get("status") == "error":
            status_code = 404 if "not found" in result["message"] else 400
            raise HTTPException(status_code=status_code, detail=result["message"])
        return result
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get(
    "/properties/{property_id}/jobs", response_model=ListJobsResponse
)
async def list_jobs(
    property_id: str,
    limit: int = Query(50, ge=1, le=500),
):
    """列出某 ComputedProperty 的任务历史"""
    try:
        result = computed_service.list_jobs(property_id, limit=limit)
        if result.get("status") == "error":
            raise HTTPException(status_code=400, detail=result["message"])
        return result
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/jobs/{job_id}")
async def get_job(job_id: str):
    """获取 MaterializationJob 状态"""
    try:
        result = computed_service.get_job_status(job_id)
        if result.get("status") == "error":
            raise HTTPException(status_code=404, detail=result["message"])
        return result
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
