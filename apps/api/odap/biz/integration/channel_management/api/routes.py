"""渠道配置 API 路由。

提供渠道配置的 CRUD、热更新、连接测试等接口。
"""

from __future__ import annotations

import logging
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from odap.infra.security.jwt_auth import get_current_user

from odap.biz.integration.channel_management.api.schemas import (
    ChannelListResponse,
    ChannelResponse,
    ChannelTypeInfo,
    CreateChannelRequest,
    EnableDisableResponse,
    ErrorResponse,
    TestConnectionResponse,
    UpdateChannelRequest,
)
from odap.biz.integration.channel_management.models.channel import ChannelType
from odap.biz.integration.channel_management.services.channel_service import ChannelService

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/channels", tags=["channels"])

# 模块级单例
_channel_service: Optional[ChannelService] = None


def get_channel_service() -> ChannelService:
    """获取渠道服务单例。"""
    global _channel_service
    if _channel_service is None:
        _channel_service = ChannelService()
    return _channel_service


def _audit(
    action: str,
    user_id: str,
    result_status: str,
    result_message: str = "",
    details: dict = None,
    workspace_id: str = "default",
) -> None:
    """审计便捷函数。"""
    try:
        from odap.infra.security.unified_audit import log_audit

        log_audit(
            action=action,
            resource="channel_management",
            user=user_id,
            service="channel_management",
            result_status=result_status,
            result_message=result_message,
            details=details or {},
            workspace_id=workspace_id,
        )
    except Exception:
        pass


def _get_user_id(user) -> str:
    """从 user 对象提取用户 ID。"""
    if isinstance(user, dict):
        return user.get("sub", "anonymous")
    return "anonymous"


@router.get("/types", response_model=list[ChannelTypeInfo])
async def list_channel_types() -> list[ChannelTypeInfo]:
    """获取所有支持的渠道类型。
    
    公开接口，无需认证。
    """
    service = get_channel_service()
    types_info = service.get_channel_types()
    return [ChannelTypeInfo(**info) for info in types_info]


@router.get("", response_model=ChannelListResponse)
async def list_channels(
    workspace_id: str = Query(..., description="工作空间 ID"),
    channel_type: Optional[str] = Query(None, description="按渠道类型过滤"),
    user=Depends(get_current_user),
) -> ChannelListResponse:
    """获取工作空间的所有渠道配置。

    注意：凭证已脱敏，AI/Agent 只能看到 has_xxx 标志。
    """
    uid = _get_user_id(user)
    try:
        ct = None
        if channel_type:
            try:
                ct = ChannelType(channel_type)
            except ValueError:
                raise HTTPException(status_code=400, detail=f"无效的渠道类型: {channel_type}")

        service = get_channel_service()
        channels = service.list_channels(workspace_id, ct)
        return ChannelListResponse(
            channels=[ChannelResponse(**ch) for ch in channels],
            total=len(channels),
        )
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"获取渠道列表失败: {e}")
        _audit("channel_list_failed", uid, "failure", str(e), {"workspace_id": workspace_id})
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/{channel_id}", response_model=ChannelResponse)
async def get_channel(
    channel_id: str,
    user=Depends(get_current_user),
) -> ChannelResponse:
    """获取单个渠道配置。"""
    uid = _get_user_id(user)
    try:
        service = get_channel_service()
        # 默认不返回实际凭证
        channel = service.get_channel(channel_id, include_credentials=False)
        if not channel:
            raise HTTPException(status_code=404, detail="渠道配置不存在")
        return ChannelResponse(**channel)
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"获取渠道配置失败: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("", response_model=ChannelResponse, status_code=201)
async def create_channel(
    request: CreateChannelRequest,
    user=Depends(get_current_user),
) -> ChannelResponse:
    """创建渠道配置。"""
    uid = _get_user_id(user)
    try:
        ct = ChannelType(request.channel_type)
    except ValueError:
        raise HTTPException(status_code=400, detail=f"无效的渠道类型: {request.channel_type}")

    try:
        service = get_channel_service()
        channel = service.create_channel(
            workspace_id=request.workspace_id,
            channel_type=ct,
            name=request.name,
            config=request.config,
            enabled=request.enabled,
            allow_from=request.allow_from,
        )
        _audit(
            "channel_create",
            uid,
            "success",
            details={"channel_id": channel["id"], "channel_type": request.channel_type},
            workspace_id=request.workspace_id,
        )
        return ChannelResponse(**channel)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"创建渠道配置失败: {e}")
        _audit(
            "channel_create_failed",
            uid,
            "failure",
            str(e),
            {"channel_type": request.channel_type},
            request.workspace_id,
        )
        raise HTTPException(status_code=500, detail=str(e))


@router.put("/{channel_id}", response_model=ChannelResponse)
async def update_channel(
    channel_id: str,
    request: UpdateChannelRequest,
    user=Depends(get_current_user),
) -> ChannelResponse:
    """更新渠道配置。"""
    uid = _get_user_id(user)
    try:
        service = get_channel_service()
        channel = service.update_channel(
            config_id=channel_id,
            name=request.name,
            config=request.config,
            enabled=request.enabled,
            allow_from=request.allow_from,
        )
        if not channel:
            raise HTTPException(status_code=404, detail="渠道配置不存在")
        _audit("channel_update", uid, "success", details={"channel_id": channel_id})
        return ChannelResponse(**channel)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"更新渠道配置失败: {e}")
        _audit("channel_update_failed", uid, "failure", str(e), {"channel_id": channel_id})
        raise HTTPException(status_code=500, detail=str(e))


@router.delete("/{channel_id}", status_code=204)
async def delete_channel(
    channel_id: str,
    user=Depends(get_current_user),
) -> None:
    """删除渠道配置。"""
    uid = _get_user_id(user)
    try:
        service = get_channel_service()
        deleted = service.delete_channel(channel_id)
        if not deleted:
            raise HTTPException(status_code=404, detail="渠道配置不存在")
        _audit("channel_delete", uid, "success", details={"channel_id": channel_id})
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"删除渠道配置失败: {e}")
        _audit("channel_delete_failed", uid, "failure", str(e), {"channel_id": channel_id})
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/{channel_id}/test", response_model=TestConnectionResponse)
async def test_connection(
    channel_id: str,
    user=Depends(get_current_user),
) -> TestConnectionResponse:
    """测试渠道连接。"""
    uid = _get_user_id(user)
    try:
        service = get_channel_service()
        result = service.test_connection(channel_id)
        _audit(
            "channel_test",
            uid,
            "success" if result["success"] else "failure",
            result.get("message", ""),
            {"channel_id": channel_id},
        )
        return TestConnectionResponse(**result)
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"测试连接失败: {e}")
        _audit("channel_test_failed", uid, "failure", str(e), {"channel_id": channel_id})
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/{channel_id}/enable", response_model=EnableDisableResponse)
async def enable_channel(
    channel_id: str,
    user=Depends(get_current_user),
) -> EnableDisableResponse:
    """启用渠道（热更新）。"""
    uid = _get_user_id(user)
    try:
        service = get_channel_service()
        channel = service.enable_channel(channel_id)
        if not channel:
            raise HTTPException(status_code=404, detail="渠道配置不存在")
        _audit("channel_enable", uid, "success", details={"channel_id": channel_id})
        return EnableDisableResponse(
            status="success",
            message="渠道已启用",
            channel=ChannelResponse(**channel),
        )
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"启用渠道失败: {e}")
        _audit("channel_enable_failed", uid, "failure", str(e), {"channel_id": channel_id})
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/{channel_id}/disable", response_model=EnableDisableResponse)
async def disable_channel(
    channel_id: str,
    user=Depends(get_current_user),
) -> EnableDisableResponse:
    """停用渠道（热更新）。"""
    uid = _get_user_id(user)
    try:
        service = get_channel_service()
        channel = service.disable_channel(channel_id)
        if not channel:
            raise HTTPException(status_code=404, detail="渠道配置不存在")
        _audit("channel_disable", uid, "success", details={"channel_id": channel_id})
        return EnableDisableResponse(
            status="success",
            message="渠道已停用",
            channel=ChannelResponse(**channel),
        )
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"停用渠道失败: {e}")
        _audit("channel_disable_failed", uid, "failure", str(e), {"channel_id": channel_id})
        raise HTTPException(status_code=500, detail=str(e))
