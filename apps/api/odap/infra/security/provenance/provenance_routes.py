"""PROV-O 溯源导出 API（扩展 ADR-074 §增补）。

端点：
- GET /api/audit/export?format=prov-o&workspace_id=...&limit=...

复用 unified_audit.get_audit_logs 查询审计事件，导出 JSON-LD / Turtle / CSV。
按 workspace_id 过滤（安全要求：隔离）。
"""

from __future__ import annotations

from typing import Optional

from fastapi import APIRouter, HTTPException, Depends, Query
from fastapi.responses import Response

from odap.infra.security.jwt_auth import get_current_user

from .audit_exporter import AuditExporter

router = APIRouter(prefix="/api/audit", tags=["audit-provenance"])


@router.get("/export")
async def export_audit(
    format: str = Query("prov-o", description="导出格式：prov-o(=json-ld) | turtle | rdfxml | csv"),
    workspace_id: str = Query("default", description="工作空间过滤"),
    limit: int = Query(100, ge=1, le=1000),
    user=Depends(get_current_user),
):
    """导出审计事件为 PROV-O 溯源（JSON-LD / Turtle / RDFXML / CSV）。

    零侵入只读旁路，不改变审计写入路径。
    """
    try:
        from odap.infra.security.unified_audit import get_audit_logs

        # 查询审计事件
        events = get_audit_logs(limit=limit)

        # 按 workspace 过滤
        filtered = [e for e in events if e.get("workspace_id", "default") == workspace_id]

        exporter = AuditExporter()

        # format 归一化：prov-o → json-ld
        fmt = "json-ld" if format == "prov-o" else format

        if fmt == "csv":
            content = exporter.export(filtered, "csv")
            return Response(
                content=content,
                media_type="text/csv",
                headers={"Content-Disposition": "attachment; filename=audit_provenance.csv"},
            )

        content = exporter.export(filtered, fmt)
        media_types = {
            "json-ld": "application/ld+json",
            "turtle": "text/turtle",
            "rdfxml": "application/rdf+xml",
        }
        if fmt not in media_types:
            raise HTTPException(status_code=400, detail=f"不支持的格式: {format}")

        return Response(
            content=content,
            media_type=media_types[fmt],
        )
    except RuntimeError as e:
        raise HTTPException(status_code=503, detail=str(e))
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


__all__ = ["router"]
