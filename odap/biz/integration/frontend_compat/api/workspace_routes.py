"""前端API兼容层 - 工作空间/审计路由"""

from fastapi import APIRouter, HTTPException, Query, Depends
from odap.infra.security.jwt_auth import get_current_user
from typing import Dict, Any, Optional
from datetime import datetime

from odap.biz.integration.frontend_compat.api._deps import (
    workspace_service,
    audit_logger,
    AuditFilter,
    AuditEventType,
    AuditSeverity,
    ActorInfo,
    ResourceInfo,
)

router = APIRouter(prefix="/api/compat", tags=["frontend-compat-workspace"])


# ==================== 工作空间路由（使用完整实现） ====================

# 注意：更具体的路由必须放在更通用的路由前面！

@router.get("/workspaces")
async def list_workspaces(user=Depends(get_current_user)):
    """列出工作空间（兼容前端）"""
    try:
        result = workspace_service.list_workspaces(filters={}, page=1, page_size=100)
        return result
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/workspaces/{workspace_id}")
async def get_workspace(workspace_id: str,
    user=Depends(get_current_user)):
    """获取工作空间（兼容前端）"""
    try:
        result = workspace_service.get_workspace(workspace_id)
        if result.get("status") == "error":
            raise HTTPException(status_code=404, detail=result.get("message"))
        return result
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# ==================== 审计日志路由 ====================

@router.get("/audit/events")
async def list_audit_events(
    start_time: Optional[str] = Query(None),
    end_time: Optional[str] = Query(None),
    event_type: Optional[str] = Query(None),
    severity: Optional[str] = Query(None),
    actor_id: Optional[str] = Query(None),
    limit: int = Query(50, ge=1, le=100),
    offset: int = Query(0, ge=0),
    user=Depends(get_current_user)):
    """列出审计事件（兼容前端）"""
    try:
        filter_kwargs = {
            "limit": limit,
            "offset": offset,
            "order_by": "timestamp",
            "order_desc": True,
        }

        if start_time:
            filter_kwargs["start_time"] = datetime.fromisoformat(start_time)
        if end_time:
            filter_kwargs["end_time"] = datetime.fromisoformat(end_time)
        if event_type:
            filter_kwargs["event_types"] = [event_type]
        if severity:
            filter_kwargs["severities"] = [severity]
        if actor_id:
            filter_kwargs["actor_ids"] = [actor_id]

        audit_filter = AuditFilter(**filter_kwargs)

        events = await audit_logger.query(audit_filter)

        event_list = []
        for event in events:
            event_dict = event.model_dump()
            if isinstance(event_dict["timestamp"], datetime):
                event_dict["timestamp"] = event_dict["timestamp"].isoformat()
            event_list.append(event_dict)

        return {
            "events": event_list,
            "total": len(event_list),
            "limit": limit,
            "offset": offset,
        }
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/audit/events")
async def create_audit_event(data: Dict[str, Any],
    user=Depends(get_current_user)):
    """创建审计事件（兼容前端）"""
    try:
        event_type_str = data.get("event_type", "system.action")
        try:
            event_type = AuditEventType(event_type_str)
        except ValueError:
            event_type = AuditEventType.SYSTEM_HEALTH

        event_id = await audit_logger.log(
            event_type=event_type,
            action=data.get("action", ""),
            resource={
                "resource_type": data.get("resource_type", ""),
                "resource_id": data.get("resource_id", ""),
                "resource_name": data.get("resource_id", ""),
            },
            result={
                "status": data.get("result_status", "success"),
                "message": data.get("result_message", ""),
            },
            severity=AuditSeverity(data.get("severity", "info")),
            actor={
                "actor_type": "user",
                "actor_id": data.get("actor_id", "system"),
                "actor_name": data.get("actor_name", "System"),
                "roles": [],
            },
            workspace_id=data.get("workspace_id", "default"),
            context=data.get("context"),
        )

        return {
            "id": event_id,
            "event_type": event_type.value,
            "action": data.get("action", ""),
            "status": "success",
        }
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/audit/timeline")
async def get_audit_timeline(
    start_time: Optional[str] = Query(None),
    end_time: Optional[str] = Query(None),
    workspace_id: Optional[str] = Query(None),
    user=Depends(get_current_user)):
    """获取审计时间线（兼容前端）"""
    try:
        filter_kwargs = {
            "limit": 100,
            "offset": 0,
            "order_by": "timestamp",
            "order_desc": True,
        }

        if start_time:
            filter_kwargs["start_time"] = datetime.fromisoformat(start_time)
        if end_time:
            filter_kwargs["end_time"] = datetime.fromisoformat(end_time)
        if workspace_id:
            filter_kwargs["workspace_id"] = workspace_id

        audit_filter = AuditFilter(**filter_kwargs)

        events = await audit_logger.query(audit_filter)

        event_list = []
        for event in events:
            event_dict = event.model_dump()
            if isinstance(event_dict["timestamp"], datetime):
                event_dict["timestamp"] = event_dict["timestamp"].isoformat()
            event_list.append(event_dict)

        return {
            "events": event_list,
            "total": len(event_list),
            "limit": 100,
            "offset": 0,
        }
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/audit/stats")
async def get_audit_stats(user=Depends(get_current_user)):
    """获取审计统计（兼容前端）"""
    try:
        stats = audit_logger.get_stats()

        return {
            "total": stats.get("total", 0),
            "by_type": stats.get("by_type", {}),
            "by_severity": stats.get("by_severity", {}),
            "by_status": {},
        }
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/audit/trace/{trace_id}")
async def get_trace_events(trace_id: str,
    user=Depends(get_current_user)):
    """获取追踪链事件（兼容前端）"""
    try:
        audit_filter = AuditFilter(
            trace_id=trace_id,
            limit=100,
            order_by="timestamp",
            order_desc=False,
        )

        events = await audit_logger.query(audit_filter)

        event_list = []
        for event in events:
            event_dict = event.model_dump()
            if isinstance(event_dict["timestamp"], datetime):
                event_dict["timestamp"] = event_dict["timestamp"].isoformat()
            event_list.append(event_dict)

        return {
            "events": event_list,
            "total": len(event_list),
        }
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
