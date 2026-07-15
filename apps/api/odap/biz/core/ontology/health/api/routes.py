"""Data Health - FastAPI 路由 (T341)

前缀: /api/ontology/health
端点：
- POST   /rules              创建规则
- GET    /rules              列出规则
- GET    /rules/{rule_id}    获取规则
- PUT    /rules/{rule_id}    更新规则
- DELETE /rules/{rule_id}    删除规则
- POST   /scan               触发扫描
- GET    /reports            列出报告
- GET    /reports/{report_id} 获取报告
"""
from __future__ import annotations

from typing import Optional

from fastapi import APIRouter, HTTPException, Query

from ..services import HealthService
from .schemas import (
    CreateHealthRuleRequest,
    ListReportsResponse,
    ListRulesResponse,
    ScanRequest,
    ScanResponse,
    UpdateHealthRuleRequest,
)


router = APIRouter(prefix="/api/ontology/health", tags=["health"])

# 模块级单例
health_service = HealthService()


# ---------- rules ----------


@router.post("/rules", response_model=ListRulesResponse)
async def create_rule(request: CreateHealthRuleRequest):
    """创建健康规则"""
    try:
        result = health_service.create_rule(request.model_dump())
        if result.get("status") == "error":
            raise HTTPException(status_code=400, detail=result["message"])
        return {"rules": [result], "count": 1}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/rules", response_model=ListRulesResponse)
async def list_rules(
    enabled_only: bool = Query(False, description="仅返回启用的规则"),
    target_type_id: Optional[str] = Query(None, description="按目标类型过滤"),
    severity: Optional[str] = Query(None, description="按严重度过滤"),
):
    """列出健康规则"""
    try:
        result = health_service.list_rules(
            enabled_only=enabled_only,
            target_type_id=target_type_id,
            severity=severity,
        )
        if result.get("status") == "error":
            raise HTTPException(status_code=400, detail=result["message"])
        return result
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/rules/{rule_id}")
async def get_rule(rule_id: str):
    """获取单条规则"""
    try:
        result = health_service.get_rule(rule_id)
        if result.get("status") == "error":
            raise HTTPException(status_code=404, detail=result["message"])
        return result
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.put("/rules/{rule_id}")
async def update_rule(rule_id: str, request: UpdateHealthRuleRequest):
    """更新规则（部分字段）"""
    try:
        payload = {k: v for k, v in request.model_dump().items() if v is not None}
        result = health_service.update_rule(rule_id, payload)
        if result.get("status") == "error":
            status_code = 404 if "not found" in result["message"] else 400
            raise HTTPException(status_code=status_code, detail=result["message"])
        return result
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.delete("/rules/{rule_id}")
async def delete_rule(rule_id: str):
    """删除规则"""
    try:
        result = health_service.delete_rule(rule_id)
        if result.get("status") == "error":
            raise HTTPException(status_code=404, detail=result["message"])
        return result
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# ---------- scan ----------


@router.post("/scan", response_model=ScanResponse)
async def trigger_scan(request: ScanRequest):
    """触发扫描"""
    try:
        result = health_service.trigger_scan(rule_id=request.rule_id)
        if result.get("status") == "error":
            raise HTTPException(status_code=400, detail=result["message"])
        return result
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# ---------- reports ----------


@router.get("/reports", response_model=ListReportsResponse)
async def list_reports(
    status: Optional[str] = Query(None, description="按 status 过滤"),
    severity: Optional[str] = Query(None, description="按 severity 过滤"),
    target_type_id: Optional[str] = Query(None, description="按 target_type_id 过滤"),
    limit: int = Query(100, ge=1, le=1000),
    offset: int = Query(0, ge=0),
):
    """列出健康报告"""
    try:
        result = health_service.list_reports(
            status=status,
            severity=severity,
            target_type_id=target_type_id,
            limit=limit,
            offset=offset,
        )
        if result.get("status") == "error":
            raise HTTPException(status_code=400, detail=result["message"])
        return result
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/reports/{report_id}")
async def get_report(report_id: str):
    """获取单条报告"""
    try:
        result = health_service.get_report(report_id)
        if result.get("status") == "error":
            raise HTTPException(status_code=404, detail=result["message"])
        return result
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
