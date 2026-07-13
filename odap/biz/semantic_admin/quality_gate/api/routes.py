"""Quality Gate + Dashboard FastAPI Routes（C1 / C2 / C5 契约）。

注册前缀：/api/semantic-admin/quality-gate  +  /api/semantic-admin/dashboard
  C1 GET  /quality-gate/reports/{cand_id}?force=      → QualityGateService.get_report
  C2 POST /quality-gate/reports                        → QualityGateService.evaluate_batch
  C5-1 GET  /dashboard/summary                         → DashboardQueryService
  C5-2 GET  /dashboard/terms-trend?days=&domain_id=    → DashboardQueryService
  C5-3 GET  /dashboard/approvals-breakdown             → DashboardQueryService

规则（对齐 AGENTS.md §附录 B 路由定义规则）：
  - except HTTPException: raise（透传已构造的 HTTP 异常）
  - 错误 404/400/409/413/500 用 HTTPException，detail 对齐 error_code 含义
  - 路由层不写业务逻辑，所有逻辑委派 services
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query, Response, status

from odap.biz.semantic_admin.quality_gate.services import (
    DashboardQueryService,
    QualityGateService,
)
from odap.infra.security.jwt_auth import get_current_user
from odap.biz.semantic_admin.usl_manager.api.routes import verify_semantic_writer

from .schemas import (
    BatchEvaluateAsyncResponse,
    BatchEvaluateRequest,
    BatchEvaluateSyncResponse,
    DashboardResponse,
    QualityReportResponse,
)

# 两个路由组：quality-gate 和 dashboard，都挂在 /api/semantic-admin 统一前缀下
router_qg = APIRouter(prefix="/api/semantic-admin/quality-gate", tags=["semantic-admin-quality-gate"])
router_dash = APIRouter(prefix="/api/semantic-admin/dashboard", tags=["semantic-admin-dashboard"])

# 模块级单例
_quality_gate_service = QualityGateService()
_dashboard_service = DashboardQueryService()


def _map_error(result: Dict[str, Any]) -> None:
    code = str(result.get("code", "UNKNOWN_ERROR"))
    msg = str(result.get("message", code))
    detail: Any = msg
    if "missing_ids" in result:
        detail = {"message": msg, "missing_ids": result["missing_ids"]}
    if code.endswith("_400"):
        raise HTTPException(status_code=400, detail=detail)
    if code.endswith("_404"):
        raise HTTPException(status_code=404, detail=detail)
    if code.endswith("_409"):
        raise HTTPException(status_code=409, detail=detail)
    if code.endswith("_413"):
        raise HTTPException(status_code=413, detail=detail)
    raise HTTPException(status_code=500, detail=detail)


# ======================================================================
# C1 GET /quality-gate/reports/{cand_id}
# ======================================================================

@router_qg.get(
    "/reports/{candidate_id}",
    response_model=QualityReportResponse,
)
async def get_quality_report(
    candidate_id: str,
    force: bool = Query(default=False, description="强制重新评估，忽略已存在的 report"),
    _user: Any = Depends(get_current_user),
) -> QualityReportResponse:
    try:
        result = _quality_gate_service.get_report(candidate_id, force=force)
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
    if isinstance(result, dict) and result.get("status") == "error":
        _map_error(result)
    try:
        return QualityReportResponse(**result)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"报告格式化失败: {e}")


# ======================================================================
# C2 POST /quality-gate/reports
# ======================================================================

@router_qg.post(
    "/reports",
    response_model=Any,
)
async def evaluate_batch(
    body: BatchEvaluateRequest,
    response: Response,
    _user: Any = Depends(verify_semantic_writer),
) -> Any:
    """C2 契约：schema_auditor+ 可触发批量重评。"""
    try:
        result = _quality_gate_service.evaluate_batch(
            candidate_ids=list(body.candidate_ids),
            sync=body.sync,
            actor_id=body.actor_id or (
                _user.get("sub") if isinstance(_user, dict) else "system"
            ),
        )
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
    if isinstance(result, dict) and result.get("status") == "error":
        _map_error(result)
    if "generated" in result:
        response.status_code = status.HTTP_200_OK
        return BatchEvaluateSyncResponse(**result).model_dump()
    response.status_code = status.HTTP_202_ACCEPTED
    return BatchEvaluateAsyncResponse(**result).model_dump()


# ======================================================================
# C5-1 GET /dashboard/summary
# ======================================================================

@router_dash.get("/summary", response_model=DashboardResponse)
async def get_dashboard_summary(
    workspace_id: Optional[str] = Query(default=None),
    _user: Any = Depends(get_current_user),
) -> DashboardResponse:
    try:
        result = _dashboard_service.get_dashboard(
            dimension="all_time",
            workspace_id=workspace_id,
            view="summary",
        )
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
    if isinstance(result, dict) and result.get("status") == "error":
        _map_error(result)
    try:
        return DashboardResponse(**result)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Dashboard 格式化失败: {e}")


# ======================================================================
# C5-2 GET /dashboard/terms-trend
# ======================================================================

@router_dash.get("/terms-trend", response_model=DashboardResponse)
async def get_dashboard_terms_trend(
    days: int = Query(default=30, ge=7, le=180, description="趋势天数 [7, 180]"),
    domain_id: Optional[str] = Query(default=None),
    workspace_id: Optional[str] = Query(default=None),
    _user: Any = Depends(get_current_user),
) -> DashboardResponse:
    try:
        result = _dashboard_service.get_dashboard(
            dimension=f"range_{days}d" if days in (7, 30) else "range_30d",
            workspace_id=workspace_id,
            view="terms_trend",
            days=days,
            domain_id=domain_id,
        )
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
    if isinstance(result, dict) and result.get("status") == "error":
        _map_error(result)
    try:
        return DashboardResponse(**result)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Dashboard 格式化失败: {e}")


# ======================================================================
# C5-3 GET /dashboard/approvals-breakdown
# ======================================================================

@router_dash.get("/approvals-breakdown", response_model=DashboardResponse)
async def get_dashboard_approvals_breakdown(
    workspace_id: Optional[str] = Query(default=None),
    _user: Any = Depends(get_current_user),
) -> DashboardResponse:
    try:
        result = _dashboard_service.get_dashboard(
            dimension="all_time",
            workspace_id=workspace_id,
            view="approvals_breakdown",
        )
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
    if isinstance(result, dict) and result.get("status") == "error":
        _map_error(result)
    try:
        return DashboardResponse(**result)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Dashboard 格式化失败: {e}")


# 构造 router = router_qg + router_dash（统一对外导出一个 router，简化 router_registry 写法）
router = APIRouter()
for r in (router_qg, router_dash):
    router.include_router(r)

__all__ = ["router", "router_qg", "router_dash"]
