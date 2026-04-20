#!/usr/bin/env python3
"""API路由 - 符合设计文档要求"""

from fastapi import APIRouter, HTTPException, Query
from typing import Dict, Any, List, Optional
from datetime import datetime
from . import (
    get_audit_logger, AuditFilter, AuditEventType, AuditSeverity,
    get_audit_logs as get_unified_audit_logs
)

router = APIRouter(prefix="/api/audit", tags=["audit"])

audit_logger = get_audit_logger()


@router.get("/events")
async def query_audit_events(
    start_time: Optional[str] = None,
    end_time: Optional[str] = None,
    event_types: Optional[List[str]] = Query(None),
    severities: Optional[List[str]] = Query(None),
    actor_ids: Optional[List[str]] = Query(None),
    actor_types: Optional[List[str]] = Query(None),
    resource_types: Optional[List[str]] = Query(None),
    resource_ids: Optional[List[str]] = Query(None),
    workspace_id: Optional[str] = None,
    trace_id: Optional[str] = None,
    result_status: Optional[List[str]] = Query(None),
    keyword: Optional[str] = None,
    limit: int = Query(50, ge=1, le=100),
    offset: int = Query(0, ge=0),
    order_by: str = Query("timestamp"),
    order_desc: bool = Query(True)
):
    """查询审计事件 - 符合设计文档"""
    try:
        # 构建过滤器
        filter_kwargs = {}
        
        if start_time:
            filter_kwargs["start_time"] = datetime.fromisoformat(start_time)
        if end_time:
            filter_kwargs["end_time"] = datetime.fromisoformat(end_time)
        if event_types:
            filter_kwargs["event_types"] = [AuditEventType(et) for et in event_types]
        if severities:
            filter_kwargs["severities"] = [AuditSeverity(s) for s in severities]
        if actor_ids:
            filter_kwargs["actor_ids"] = actor_ids
        if actor_types:
            filter_kwargs["actor_types"] = actor_types
        if resource_types:
            filter_kwargs["resource_types"] = resource_types
        if resource_ids:
            filter_kwargs["resource_ids"] = resource_ids
        if workspace_id:
            filter_kwargs["workspace_id"] = workspace_id
        if trace_id:
            filter_kwargs["trace_id"] = trace_id
        if result_status:
            filter_kwargs["result_status"] = result_status
        if keyword:
            filter_kwargs["keyword"] = keyword
        
        filter_kwargs.update({
            "limit": limit,
            "offset": offset,
            "order_by": order_by,
            "order_desc": order_desc
        })
        
        # 创建过滤器
        audit_filter = AuditFilter(**filter_kwargs)
        
        # 查询事件
        events = await audit_logger.query(audit_filter)
        
        # 转换为前端友好的格式
        result = []
        for event in events:
            event_dict = event.model_dump()
            # 转换datetime为字符串
            if isinstance(event_dict["timestamp"], datetime):
                event_dict["timestamp"] = event_dict["timestamp"].isoformat()
            result.append(event_dict)
        
        return {
            "total": len(result),
            "items": result,
            "limit": limit,
            "offset": offset
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/events/{event_id}")
async def get_audit_event(event_id: str):
    """获取事件详情 - 符合设计文档"""
    try:
        # 构建过滤器
        audit_filter = AuditFilter(
            limit=1,
            offset=0
        )
        
        # 查询事件
        events = await audit_logger.query(audit_filter)
        
        # 查找指定ID的事件
        for event in events:
            if event.id == event_id:
                event_dict = event.model_dump()
                if isinstance(event_dict["timestamp"], datetime):
                    event_dict["timestamp"] = event_dict["timestamp"].isoformat()
                return event_dict
        
        raise HTTPException(status_code=404, detail="Event not found")
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/timeline")
async def get_audit_timeline(
    start_time: Optional[str] = None,
    end_time: Optional[str] = None,
    workspace_id: Optional[str] = None,
    limit: int = Query(100, ge=1, le=500)
):
    """时间线视图 - 符合设计文档"""
    try:
        # 构建过滤器
        filter_kwargs = {
            "limit": limit,
            "order_by": "timestamp",
            "order_desc": True
        }
        
        if start_time:
            filter_kwargs["start_time"] = datetime.fromisoformat(start_time)
        if end_time:
            filter_kwargs["end_time"] = datetime.fromisoformat(end_time)
        if workspace_id:
            filter_kwargs["workspace_id"] = workspace_id
        
        audit_filter = AuditFilter(**filter_kwargs)
        
        # 查询事件
        events = await audit_logger.query(audit_filter)
        
        # 转换为时间线格式
        timeline = []
        for event in events:
            timeline.append({
                "id": event.id,
                "timestamp": event.timestamp.isoformat(),
                "event_type": event.event_type.value,
                "action": event.action,
                "actor": event.actor.actor_name,
                "resource": event.resource.resource_name,
                "result": event.result.status,
                "duration_ms": event.duration_ms
            })
        
        return {"timeline": timeline}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/trace/{trace_id}")
async def get_audit_trace(trace_id: str):
    """追踪链查询 - 符合设计文档"""
    try:
        # 构建过滤器
        audit_filter = AuditFilter(
            trace_id=trace_id,
            limit=100,
            order_by="timestamp",
            order_desc=False
        )
        
        # 查询事件
        events = await audit_logger.query(audit_filter)
        
        # 构建追踪链
        trace_chain = []
        for event in events:
            trace_chain.append({
                "id": event.id,
                "timestamp": event.timestamp.isoformat(),
                "event_type": event.event_type.value,
                "action": event.action,
                "actor": event.actor.actor_name,
                "resource": event.resource.resource_name,
                "result": event.result.status,
                "parent_event_id": event.parent_event_id,
                "duration_ms": event.duration_ms
            })
        
        return {"trace_id": trace_id, "chain": trace_chain}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/stats")
async def get_audit_stats(
    start_time: Optional[str] = None,
    end_time: Optional[str] = None
):
    """审计统计 - 符合设计文档"""
    try:
        # 获取统计信息
        stats = audit_logger.get_stats()
        
        # 转换为设计文档要求的格式
        return {
            "total": stats.get("total", 0),
            "by_severity": stats.get("by_severity", {}),
            "by_type": stats.get("by_type", {}),
            "time_range": {
                "start": start_time or "all",
                "end": end_time or "all"
            }
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/export")
async def export_audit_logs(
    start_time: Optional[str] = None,
    end_time: Optional[str] = None,
    event_types: Optional[List[str]] = None,
    severities: Optional[List[str]] = None,
    format: str = "json"
):
    """导出审计日志 - 符合设计文档"""
    try:
        # 构建过滤器
        filter_kwargs = {
            "limit": 1000,  # 限制导出数量
            "order_by": "timestamp",
            "order_desc": True
        }
        
        if start_time:
            filter_kwargs["start_time"] = datetime.fromisoformat(start_time)
        if end_time:
            filter_kwargs["end_time"] = datetime.fromisoformat(end_time)
        if event_types:
            filter_kwargs["event_types"] = [AuditEventType(et) for et in event_types]
        if severities:
            filter_kwargs["severities"] = [AuditSeverity(s) for s in severities]
        
        audit_filter = AuditFilter(**filter_kwargs)
        
        # 查询事件
        events = await audit_logger.query(audit_filter)
        
        # 转换为导出格式
        export_data = []
        for event in events:
            event_dict = event.model_dump()
            if isinstance(event_dict["timestamp"], datetime):
                event_dict["timestamp"] = event_dict["timestamp"].isoformat()
            export_data.append(event_dict)
        
        if format == "json":
            return {"format": "json", "data": export_data, "count": len(export_data)}
        else:
            raise HTTPException(status_code=400, detail="Unsupported format")
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# 兼容旧版本的路由（保持向后兼容）
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
    """记录日志（兼容旧版本）"""
    try:
        from . import ActorInfo, ResourceInfo, ActionResult
        
        # 转换为新的事件格式
        await audit_logger.log(
            event_type=AuditEventType.SYSTEM_HEALTH,
            action=action,
            resource=ResourceInfo(
                resource_type="resource",
                resource_id=resource or "unknown",
                resource_name=resource or "Unknown"
            ),
            result=ActionResult(
                status="success",
                message="Log created"
            ),
            actor=ActorInfo(
                actor_type="user",
                actor_id=user or "anonymous",
                actor_name=user or "Anonymous",
                roles=[]
            ),
            context=details or {},
            severity=AuditSeverity(level.lower())
        )
        
        return {"status": "success", "message": "Log created"}
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
    """查询日志（兼容旧版本）"""
    try:
        # 构建过滤器
        filter_kwargs = {
            "limit": page_size,
            "offset": (page - 1) * page_size,
            "order_by": "timestamp",
            "order_desc": True
        }
        
        if level:
            filter_kwargs["severities"] = [AuditSeverity(level.lower())]
        if user:
            filter_kwargs["actor_ids"] = [user]
        
        audit_filter = AuditFilter(**filter_kwargs)
        
        # 查询事件
        events = await audit_logger.query(audit_filter)
        
        # 转换为旧格式
        logs = []
        for event in events:
            logs.append({
                "id": event.id,
                "timestamp": event.timestamp.isoformat(),
                "level": event.severity.value,
                "type": event.event_type.value,
                "service": "audit",
                "action": event.action,
                "details": event.context,
                "user": event.actor.actor_id,
                "resource": event.resource.resource_id
            })
        
        return {
            "total": len(logs),
            "page": page,
            "page_size": page_size,
            "items": logs
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
