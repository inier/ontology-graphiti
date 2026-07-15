"""配置管理路由"""

import asyncio
import logging
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query

from odap.biz.platform.config.api.schemas import (
    UpdateConfigRequest, UpdateConfigResponse, ServiceConfigResponse,
    ConfigItemResponse, ConfigValidationResultResponse, TestConnectionRequest,
    RollbackRequest, ImportConfigRequest, ConfigHistoryResponse, ConfigStatusItem,
)
from odap.biz.platform.config.services.config_service import ConfigService
from odap.biz.platform.config.models.config_models import ServiceCategory

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/config", tags=["config"])

_config_service: Optional[ConfigService] = None


def _get_service() -> ConfigService:
    global _config_service
    if _config_service is None:
        _config_service = ConfigService()
    return _config_service


def _verify_admin():
    """验证 admin 角色"""
    try:
        from odap.infra.security.auth_routes import verify_admin
        return Depends(verify_admin)
    except ImportError:
        return None


# ── 静态路径路由（必须在 /{category} 之前定义） ──


@router.get("", response_model=dict)
async def get_all_configs():
    """获取所有配置（脱敏）"""
    try:
        service = _get_service()
        configs = service.get_all_configs()
        result = []
        for cfg in configs:
            items = [
                ConfigItemResponse(
                    key=item.key,
                    display_value=item.display_value,
                    value_type=item.value_type.value,
                    label=item.label,
                    description=item.description,
                    is_sensitive=item.is_sensitive,
                    is_required=item.is_required,
                    default_value=item.default_value,
                    choices=item.choices,
                    min_val=item.min_val,
                    max_val=item.max_val,
                    sort_order=item.sort_order,
                    group=item.group,
                    has_value=item.has_value,
                ).model_dump()
                for item in cfg.items
            ]
            result.append(ServiceConfigResponse(
                category=cfg.category.value,
                label=cfg.label,
                description=cfg.description,
                icon=cfg.icon,
                items=items,
                connection_status=cfg.connection_status.value,
                last_tested_at=cfg.last_tested_at,
                last_error=cfg.last_error,
            ).model_dump())
        return {"categories": result}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/status")
async def get_config_status():
    """获取配置状态总览"""
    try:
        service = _get_service()
        return {"statuses": service.get_config_status()}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/history")
async def get_config_history(
    category: Optional[str] = None,
    limit: int = Query(default=50, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
):
    """查询变更历史"""
    try:
        service = _get_service()
        return service.list_revisions(category, limit, offset)
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/export")
async def export_configs():
    """导出配置"""
    try:
        service = _get_service()
        return service.export_configs()
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# ── 动态路径路由（必须在静态路径之后） ──


@router.get("/{category}")
async def get_configs_by_category(category: str):
    """获取指定服务类别的配置"""
    try:
        service = _get_service()
        cfg = service.get_configs_by_category(category)
        if not cfg:
            raise HTTPException(status_code=404, detail=f"Unknown category: {category}")
        items = [
            ConfigItemResponse(
                key=item.key,
                display_value=item.display_value,
                value_type=item.value_type.value,
                label=item.label,
                description=item.description,
                is_sensitive=item.is_sensitive,
                is_required=item.is_required,
                default_value=item.default_value,
                choices=item.choices,
                min_val=item.min_val,
                max_val=item.max_val,
                sort_order=item.sort_order,
                group=item.group,
                has_value=item.has_value,
            ).model_dump()
            for item in cfg.items
        ]
        return ServiceConfigResponse(
            category=cfg.category.value,
            label=cfg.label,
            description=cfg.description,
            icon=cfg.icon,
            items=items,
            connection_status=cfg.connection_status.value,
            last_tested_at=cfg.last_tested_at,
            last_error=cfg.last_error,
        ).model_dump()
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# ── 写操作路由 ──


@router.put("")
async def update_configs(request: UpdateConfigRequest):
    """批量更新配置"""
    try:
        service = _get_service()
        result = await service.update_configs(
            items=[item.model_dump() for item in request.items],
            test_connection=request.test_connection,
            operator_id="admin",  # TODO: 从 JWT 获取
            operator_name="admin",
        )
        if result.get("status") == "error":
            raise HTTPException(status_code=400, detail=result.get("message", "Update failed"))
        if result.get("status") == "validation_failed":
            raise HTTPException(status_code=400, detail="Connection validation failed")
        return result
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/test")
async def test_connection(request: TestConnectionRequest):
    """测试服务连接"""
    try:
        service = _get_service()
        categories = request.categories or [cat.value for cat in ServiceCategory]
        items = [item.model_dump() for item in request.items] if request.items else None
        results = await service.test_connection(categories, items)
        return {"results": results}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/rollback")
async def rollback_config(request: RollbackRequest):
    """回滚配置"""
    try:
        service = _get_service()
        result = await service.rollback_to_revision(
            request.revision_number,
            operator_id="admin",
            operator_name="admin",
        )
        if result.get("status") == "error":
            raise HTTPException(status_code=404, detail=result.get("message", "Revision not found"))
        return result
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/import")
async def import_configs(request: ImportConfigRequest):
    """导入配置"""
    try:
        service = _get_service()
        result = service.import_configs(
            items=[item.model_dump() for item in request.items],
            operator_id="admin",
            operator_name="admin",
        )
        return result
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
