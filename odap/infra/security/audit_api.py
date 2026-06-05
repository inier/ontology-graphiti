#!/usr/bin/env python3
"""API路由 - 审计日志

统一使用 SQLiteAuditChannel 单例，与 unified_audit.py 写入同一数据库。
"""

from fastapi import APIRouter, HTTPException, Query, Depends
from odap.infra.security.jwt_auth import get_current_user
from typing import Dict, Any, List, Optional
from datetime import datetime
import sqlite3

from .audit_sqlite_channel import get_sqlite_audit_channel
from .audit_models import AuditFilter, AuditEventType, AuditSeverity
from .unified_audit import get_audit_logs as get_unified_audit_logs

router = APIRouter(prefix="/api/audit", tags=["audit"])

_sqlite_channel = None

_SEVERITY_ALIASES = {
    "warning": "warn",
    "warn": "warn",
    "debug": "debug",
    "info": "info",
    "error": "error",
    "critical": "critical",
}

_EVENT_TYPE_ALIASES = {
    "system.startup": "system.health",
    "system.shutdown": "system.health",
    "system.action": "system.health",
    "workspace.update": "workspace.create",
    "user.create": "user.create",
    "user.update": "user.update",
    "user.delete": "user.delete",
}


def _get_channel():
    global _sqlite_channel
    if _sqlite_channel is None:
        _sqlite_channel = get_sqlite_audit_channel()
    return _sqlite_channel


def _normalize_severity(raw: str) -> str:
    return _SEVERITY_ALIASES.get(raw.lower(), raw.lower())


def _normalize_event_type(raw: str) -> str:
    return _EVENT_TYPE_ALIASES.get(raw.lower(), raw.lower())


def _event_to_flat_dict(event) -> Dict[str, Any]:
    event_dict = event.model_dump()
    if isinstance(event_dict["timestamp"], datetime):
        event_dict["timestamp"] = event_dict["timestamp"].isoformat()
    actor = event_dict.pop("actor", {})
    resource = event_dict.pop("resource", {})
    res = event_dict.pop("result", {})
    event_dict["actor_type"] = actor.get("actor_type", "")
    event_dict["actor_id"] = actor.get("actor_id", "")
    event_dict["actor_name"] = actor.get("actor_name", "")
    event_dict["actor_roles"] = actor.get("roles", [])
    event_dict["resource_type"] = resource.get("resource_type", "")
    event_dict["resource_id"] = resource.get("resource_id", "")
    event_dict["resource_name"] = resource.get("resource_name", "")
    event_dict["result_status"] = res.get("status", "")
    event_dict["result_message"] = res.get("message", "")
    event_dict["result_error_code"] = res.get("error_code")
    event_dict["result_changes"] = res.get("changes")
    return event_dict


def _get_total_count(channel, filter_kwargs: dict) -> int:
    conn = sqlite3.connect(channel.db_path)
    cursor = conn.cursor()
    try:
        where_clauses = []
        params = []
        if "start_time" in filter_kwargs and filter_kwargs["start_time"]:
            where_clauses.append('timestamp >= ?')
            params.append(filter_kwargs["start_time"].isoformat())
        if "end_time" in filter_kwargs and filter_kwargs["end_time"]:
            where_clauses.append('timestamp <= ?')
            params.append(filter_kwargs["end_time"].isoformat())
        if "event_types" in filter_kwargs and filter_kwargs["event_types"]:
            placeholders = ','.join(['?'] * len(filter_kwargs["event_types"]))
            where_clauses.append(f'event_type IN ({placeholders})')
            params.extend([e.value for e in filter_kwargs["event_types"]])
        if "severities" in filter_kwargs and filter_kwargs["severities"]:
            placeholders = ','.join(['?'] * len(filter_kwargs["severities"]))
            where_clauses.append(f'severity IN ({placeholders})')
            params.extend([s.value for s in filter_kwargs["severities"]])
        if "actor_ids" in filter_kwargs and filter_kwargs["actor_ids"]:
            placeholders = ','.join(['?'] * len(filter_kwargs["actor_ids"]))
            where_clauses.append(f'actor_id IN ({placeholders})')
            params.extend(filter_kwargs["actor_ids"])
        if "workspace_id" in filter_kwargs and filter_kwargs["workspace_id"]:
            where_clauses.append('workspace_id = ?')
            params.append(filter_kwargs["workspace_id"])
        if "trace_id" in filter_kwargs and filter_kwargs["trace_id"]:
            where_clauses.append('trace_id = ?')
            params.append(filter_kwargs["trace_id"])
        if "result_status" in filter_kwargs and filter_kwargs["result_status"]:
            placeholders = ','.join(['?'] * len(filter_kwargs["result_status"]))
            where_clauses.append(f'result_status IN ({placeholders})')
            params.extend(filter_kwargs["result_status"])

        where_part = ' WHERE ' + ' AND '.join(where_clauses) if where_clauses else ''
        cursor.execute(f'SELECT COUNT(*) FROM audit_events{where_part}', params)
        return cursor.fetchone()[0]
    except Exception:
        return 0
    finally:
        conn.close()


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
    order_desc: bool = Query(True),
    user=Depends(get_current_user)):
    try:
        filter_kwargs = {}

        if start_time:
            filter_kwargs["start_time"] = datetime.fromisoformat(start_time)
        if end_time:
            filter_kwargs["end_time"] = datetime.fromisoformat(end_time)
        if event_types:
            normalized = []
            for et in event_types:
                mapped = _normalize_event_type(et)
                try:
                    normalized.append(AuditEventType(mapped))
                except ValueError:
                    pass
            if normalized:
                filter_kwargs["event_types"] = normalized
        if severities:
            normalized = []
            for s in severities:
                mapped = _normalize_severity(s)
                try:
                    normalized.append(AuditSeverity(mapped))
                except ValueError:
                    pass
            if normalized:
                filter_kwargs["severities"] = normalized
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

        audit_filter = AuditFilter(**filter_kwargs)

        channel = _get_channel()
        events = await channel.query(audit_filter)

        total_count = _get_total_count(channel, filter_kwargs)

        result = [_event_to_flat_dict(event) for event in events]

        return {
            "total": total_count,
            "events": result,
            "limit": limit,
            "offset": offset
        }
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/events/{event_id}")
async def get_audit_event(event_id: str,
    user=Depends(get_current_user)):
    try:
        channel = _get_channel()
        audit_filter = AuditFilter(limit=10000, offset=0)
        events = await channel.query(audit_filter)

        for event in events:
            if event.id == event_id:
                return _event_to_flat_dict(event)

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
    limit: int = Query(100, ge=1, le=500),
    user=Depends(get_current_user)):
    try:
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

        channel = _get_channel()
        events = await channel.query(audit_filter)

        result = [_event_to_flat_dict(event) for event in events]

        total_count = _get_total_count(channel, filter_kwargs)

        return {
            "events": result,
            "total": total_count
        }
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/trace/{trace_id}")
async def get_audit_trace(trace_id: str,
    user=Depends(get_current_user)):
    try:
        audit_filter = AuditFilter(
            trace_id=trace_id,
            limit=100,
            order_by="timestamp",
            order_desc=False
        )

        channel = _get_channel()
        events = await channel.query(audit_filter)

        trace_chain = []
        for event in events:
            flat = _event_to_flat_dict(event)
            trace_chain.append(flat)

        return {"trace_id": trace_id, "chain": trace_chain}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/stats")
async def get_audit_stats(
    start_time: Optional[str] = None,
    end_time: Optional[str] = None,
    user=Depends(get_current_user)):
    try:
        channel = _get_channel()

        conn = sqlite3.connect(channel.db_path)
        cursor = conn.cursor()

        try:
            where_clauses = []
            params = []
            if start_time:
                where_clauses.append('timestamp >= ?')
                params.append(datetime.fromisoformat(start_time).isoformat())
            if end_time:
                where_clauses.append('timestamp <= ?')
                params.append(datetime.fromisoformat(end_time).isoformat())

            where_part = ' WHERE ' + ' AND '.join(where_clauses) if where_clauses else ''

            cursor.execute(f'SELECT COUNT(*) FROM audit_events{where_part}', params)
            total = cursor.fetchone()[0]

            cursor.execute(f'SELECT severity, COUNT(*) FROM audit_events{where_part} GROUP BY severity', params)
            by_severity = dict(cursor.fetchall())

            cursor.execute(f'SELECT event_type, COUNT(*) FROM audit_events{where_part} GROUP BY event_type', params)
            by_type = dict(cursor.fetchall())

            cursor.execute(f'SELECT result_status, COUNT(*) FROM audit_events{where_part} GROUP BY result_status', params)
            by_status = dict(cursor.fetchall())

            return {
                "total": total,
                "by_severity": by_severity,
                "by_type": by_type,
                "by_status": by_status,
                "time_range": {
                    "start": start_time or "all",
                    "end": end_time or "all"
                }
            }
        finally:
            conn.close()
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/export")
async def export_audit_logs(
    start_time: Optional[str] = None,
    end_time: Optional[str] = None,
    event_types: Optional[List[str]] = None,
    severities: Optional[List[str]] = None,
    format: str = "json",
    user=Depends(get_current_user)):
    try:
        filter_kwargs = {
            "limit": 1000,
            "order_by": "timestamp",
            "order_desc": True
        }

        if start_time:
            filter_kwargs["start_time"] = datetime.fromisoformat(start_time)
        if end_time:
            filter_kwargs["end_time"] = datetime.fromisoformat(end_time)
        if event_types:
            normalized = []
            for et in event_types:
                mapped = _normalize_event_type(et)
                try:
                    normalized.append(AuditEventType(mapped))
                except ValueError:
                    pass
            if normalized:
                filter_kwargs["event_types"] = normalized
        if severities:
            normalized = []
            for s in severities:
                mapped = _normalize_severity(s)
                try:
                    normalized.append(AuditSeverity(mapped))
                except ValueError:
                    pass
            if normalized:
                filter_kwargs["severities"] = normalized

        audit_filter = AuditFilter(**filter_kwargs)

        channel = _get_channel()
        events = await channel.query(audit_filter)

        export_data = [_event_to_flat_dict(event) for event in events]

        if format == "json":
            return {"format": "json", "data": export_data, "count": len(export_data)}
        else:
            raise HTTPException(status_code=400, detail="Unsupported format")
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/logs")
async def create_log(
    level: str,
    log_type: str,
    service: str,
    action: str,
    details: Optional[Dict[str, Any]] = None,
    resource: Optional[str] = None,
    user=Depends(get_current_user)):
    try:
        from .unified_audit import log_audit
        log_audit(
            action=action,
            resource=resource or "unknown",
            user=user,
            service=service,
            details=details or {}
        )
        return {"status": "success", "message": "Log created"}
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
    actor: Optional[str] = None,
    action: Optional[str] = None,
    result: Optional[str] = None,
    user=Depends(get_current_user)):
    try:
        filter_kwargs = {
            "limit": page_size,
            "offset": (page - 1) * page_size,
            "order_by": "timestamp",
            "order_desc": True
        }

        if level:
            mapped = _normalize_severity(level)
            try:
                filter_kwargs["severities"] = [AuditSeverity(mapped)]
            except ValueError:
                pass
        if user:
            filter_kwargs["actor_ids"] = [user]
        if actor:
            existing = filter_kwargs.get("actor_ids", [])
            existing.append(actor)
            filter_kwargs["actor_ids"] = existing
        if action:
            filter_kwargs["keyword"] = action
        if result:
            filter_kwargs["result_status"] = [result]

        audit_filter = AuditFilter(**filter_kwargs)

        channel = _get_channel()
        events = await channel.query(audit_filter)

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
                "resource": event.resource.resource_id,
                "result_status": event.result.status,
            })

        total_count = _get_total_count(channel, filter_kwargs)

        return {
            "total": total_count,
            "page": page,
            "page_size": page_size,
            "items": logs
        }
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/timeline/resource/{resource_id}")
async def get_resource_timeline(
    resource_id: str,
    limit: int = Query(100, ge=1, le=500),
    user=Depends(get_current_user)):
    try:
        filter_kwargs = {
            "limit": limit,
            "order_by": "timestamp",
            "order_desc": True,
            "resource_ids": [resource_id],
        }

        audit_filter = AuditFilter(**filter_kwargs)

        channel = _get_channel()
        events = await channel.query(audit_filter)

        result = [_event_to_flat_dict(event) for event in events]

        total_count = _get_total_count(channel, filter_kwargs)

        return {
            "resource_id": resource_id,
            "events": result,
            "total": total_count,
        }
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
