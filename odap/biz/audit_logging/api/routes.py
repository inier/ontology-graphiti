"""API路由"""

from fastapi import APIRouter, HTTPException, Query
from typing import Dict, Any, List, Optional
from ..services.audit_service import AuditService
from ..services.channel_service import ChannelService
from ..services.validation_service import ValidationService
from ..models.log import LogLevel, LogType, LogStatus
from ..models.channel import ChannelType, ChannelStatus

router = APIRouter(prefix="/api/audit", tags=["audit"])

audit_service = AuditService()
channel_service = ChannelService()
validation_service = ValidationService()


@router.post("/logs")
async def create_log(
    level: str,
    log_type: str,
    service: str,
    action: str,
    details: Optional[Dict[str, Any]] = None,
    user: Optional[str] = None,
    resource: Optional[str] = None
):
    """记录日志"""
    try:
        result = audit_service.log(
            level=LogLevel(level),
            log_type=LogType(log_type),
            service=service,
            action=action,
            details=details,
            user=user,
            resource=resource
        )
        return result
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/logs/{log_id}")
async def get_log(log_id: str):
    """获取日志"""
    try:
        result = audit_service.get_log(log_id)
        if result.get("status") == "error":
            raise HTTPException(status_code=404, detail=result.get("message"))
        return result
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/logs")
async def query_logs(
    page: int = Query(1, ge=1),
    page_size: int = Query(10, ge=1, le=100),
    level: Optional[str] = None,
    log_type: Optional[str] = None,
    service: Optional[str] = None,
    user: Optional[str] = None
):
    """查询日志"""
    try:
        filters = {}
        if level:
            filters["level"] = level
        if log_type:
            filters["type"] = log_type
        if service:
            filters["service"] = service
        if user:
            filters["user"] = user
        
        return audit_service.query_logs(filters, page, page_size)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/stats")
async def get_stats(start_time: Optional[str] = None, end_time: Optional[str] = None):
    """获取日志统计"""
    try:
        return audit_service.get_stats(start_time, end_time)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/channels")
async def create_channel(
    name: str,
    channel_type: str = "memory",
    capacity: int = 10000,
    config: Optional[Dict[str, Any]] = None
):
    """创建通道"""
    try:
        return channel_service.create_channel(
            name=name,
            channel_type=ChannelType(channel_type),
            capacity=capacity,
            config=config
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/channels/{channel_id}")
async def get_channel(channel_id: str):
    """获取通道"""
    try:
        result = channel_service.get_channel(channel_id)
        if result.get("status") == "error":
            raise HTTPException(status_code=404, detail=result.get("message"))
        return result
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/channels/{channel_id}/enqueue")
async def enqueue(channel_id: str, item: Dict[str, Any]):
    """入队"""
    try:
        result = channel_service.enqueue(channel_id, item)
        if result.get("status") == "error":
            raise HTTPException(status_code=400, detail=result.get("message"))
        return result
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/channels/{channel_id}/dequeue")
async def dequeue(channel_id: str):
    """出队"""
    try:
        result = channel_service.dequeue(channel_id)
        if result.get("status") == "error":
            raise HTTPException(status_code=400, detail=result.get("message"))
        return result
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/channels/{channel_id}/flush")
async def flush(channel_id: str):
    """刷新通道"""
    try:
        return channel_service.flush(channel_id)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/validation/logs/{log_id}")
async def validate_log(log_id: str):
    """验证日志"""
    try:
        return validation_service.validate_log(log_id)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/validation/chains")
async def create_chain(name: str, validation_enabled: bool = True):
    """创建链"""
    try:
        return validation_service.create_chain(name, validation_enabled)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/validation/chains/{chain_id}/blocks")
async def create_block(chain_id: str, log_ids: List[str]):
    """创建区块"""
    try:
        return validation_service.create_block(chain_id, log_ids)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/validation/chains/{chain_id}/verify")
async def verify_chain(chain_id: str):
    """验证链"""
    try:
        return validation_service.verify_chain(chain_id)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/validation/chains/{chain_id}/stats")
async def get_chain_stats(chain_id: str):
    """获取链统计"""
    try:
        return validation_service.get_chain_stats(chain_id)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/validation/tampering/{log_id}")
async def detect_tampering(log_id: str):
    """检测篡改"""
    try:
        return validation_service.detect_tampering(log_id)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
