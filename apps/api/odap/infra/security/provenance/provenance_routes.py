"""PROV-O 溯源导出与完整性校验 API（扩展 ADR-074 §增补）。

端点：
- GET  /api/audit/export                 导出 JSON-LD / Turtle / RDFXML / CSV
- POST /api/audit/provenance/seal        把当前审计窗口追加封存进溯源链
- GET  /api/audit/provenance/verify      复算内容指纹并校验链路

复用 unified_audit.get_audit_logs 查询审计事件，导出 JSON-LD / Turtle / CSV。
按 workspace_id 过滤（安全要求：隔离）。

封存是显式写操作（POST）：导出与校验都保持只读，避免 GET 产生副作用。
"""

from __future__ import annotations

from typing import Any, Dict, List

from fastapi import APIRouter, HTTPException, Depends, Query
from fastapi.responses import Response

from odap.infra.security.jwt_auth import get_current_user

from .audit_exporter import AuditExporter
from .chain_store import ProvenanceChainStore

router = APIRouter(prefix="/api/audit", tags=["audit-provenance"])


def _load_workspace_events(workspace_id: str, limit: int) -> List[Dict[str, Any]]:
    """读取审计窗口并按工作空间隔离。"""
    from odap.infra.security.unified_audit import get_audit_logs

    events = get_audit_logs(limit=limit)
    return [e for e in events if e.get("workspace_id", "default") == workspace_id]


def _get_store() -> ProvenanceChainStore:
    """溯源链存储工厂（测试可替换）。"""
    return ProvenanceChainStore()


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
        # 查询审计事件
        filtered = _load_workspace_events(workspace_id, limit)

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

        media_types = {
            "json-ld": "application/ld+json",
            "turtle": "text/turtle",
            "rdfxml": "application/rdf+xml",
        }
        if fmt not in media_types:
            raise HTTPException(status_code=400, detail=f"不支持的格式: {format}")

        content = exporter.export(filtered, fmt)
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


@router.post("/provenance/seal")
async def seal_provenance(
    workspace_id: str = Query("default", description="工作空间过滤"),
    limit: int = Query(1000, ge=1, le=10000),
    user=Depends(get_current_user),
):
    """把当前审计窗口追加封存进溯源链（追加式，不覆盖已封存事件）。"""
    try:
        user_id = user.get("sub", "anonymous") if isinstance(user, dict) else "anonymous"
        events = _load_workspace_events(workspace_id, limit)
        if not events:
            return {
                "status": "error",
                "message": "审计窗口为空，无可封存事件",
                "sealed": 0,
                "skipped": 0,
            }

        store = _get_store()
        result = store.seal(events)
        result["workspace_id"] = workspace_id
        result["checked"] = len(events)

        from odap.infra.security.unified_audit import log_audit
        log_audit(
            action="provenance_seal",
            resource="audit_provenance",
            user=user_id,
            service="audit",
            details={
                "workspace_id": workspace_id,
                "sealed": result.get("sealed"),
                "skipped": result.get("skipped"),
                "head_chain_hash": (result.get("head") or {}).get("chain_hash"),
            },
            workspace_id=workspace_id,
        )
        return result
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/provenance/verify")
async def verify_provenance(
    workspace_id: str = Query("default", description="工作空间过滤"),
    limit: int = Query(1000, ge=1, le=10000),
    user=Depends(get_current_user),
):
    """复算审计记录的内容指纹，并与已封存溯源链比对。

    ``valid`` 仅在「窗口内全部已封存 + 内容指纹一致 + 链路自洽」时为 true；
    ``reason`` 会明确给出 ``unsealed`` / ``tampered`` / ``broken_chain`` /
    ``empty_window``，不做「没发现问题即通过」的含糊判断。
    """
    try:
        events = _load_workspace_events(workspace_id, limit)
        store = _get_store()
        result = store.verify(events)
        result["workspace_id"] = workspace_id
        return result
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


__all__ = ["router"]
