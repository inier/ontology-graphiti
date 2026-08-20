"""OPA API routes — PEP 评估 + 指标 + 健康"""
from fastapi import APIRouter, Depends
from pydantic import BaseModel, Field
from typing import Dict, Any, Optional
from odap.infra.security.jwt_auth import get_current_user

router = APIRouter(prefix="/api/opa", tags=["opa"])


class PEPEvaluateRequest(BaseModel):
    """PEP 评估请求"""
    agent_id: str = Field(..., description="Agent 标识")
    tool_name: str = Field(..., description="工具名称")
    action: str = Field(..., description="操作类型")
    resource: Dict[str, Any] = Field(default_factory=dict, description="资源信息")
    subject: Dict[str, Any] = Field(default_factory=dict, description="主体信息")
    environment: Dict[str, Any] = Field(default_factory=dict, description="环境信息")
    input_context: Dict[str, Any] = Field(default_factory=dict, description="输入参数")
    trace_id: str = ""
    session_id: str = ""


@router.post("/pep/evaluate")
async def pep_evaluate(req: PEPEvaluateRequest, user=Depends(get_current_user)):
    """PEP 统一评估入口 — 白名单 → OPA → 决策"""
    from odap.infra.opa.pep import get_pep_instance, EnforcementRequest

    pep = get_pep_instance()
    result = pep.evaluate(EnforcementRequest(
        agent_id=req.agent_id,
        tool_name=req.tool_name,
        action=req.action,
        resource=req.resource,
        subject=req.subject,
        environment=req.environment,
        input_context=req.input_context,
        trace_id=req.trace_id,
        session_id=req.session_id,
    ))
    return {
        "allowed": result.allowed,
        "reason": result.reason,
        "stage": result.stage,
        "blocked_at": result.blocked_at,
        "opa_decision": result.opa_decision,
    }


@router.get("/metrics")
async def opa_metrics(window: int = 300, user=Depends(get_current_user)):
    """获取 OPA 决策指标（默认 5 分钟窗口）"""
    from odap.infra.opa.metrics import get_metrics
    return get_metrics(window)


@router.get("/health")
async def opa_health(user=Depends(get_current_user)):
    """OPA 服务健康状态"""
    from odap.infra.opa.opa_service import OPAManager
    mgr = OPAManager()
    return {
        "opa_reachable": not getattr(mgr, '_opa_unavailable', False),
        "bundle_version": mgr.get_bundle_version(),
        "mode": "mock" if mgr.use_mock else "opa",
    }
