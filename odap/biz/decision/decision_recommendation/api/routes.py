from fastapi import APIRouter, HTTPException, Depends
from odap.infra.security.jwt_auth import get_current_user
from pydantic import BaseModel, Field
from typing import Dict, Any, List, Optional

from ..engine import DecisionRecommendationEngine

router = APIRouter(prefix="/api/decision", tags=["decision"])

_engine: Optional[DecisionRecommendationEngine] = None


def _get_engine() -> DecisionRecommendationEngine:
    global _engine
    if _engine is None:
        _engine = DecisionRecommendationEngine()
    return _engine


def _audit(action: str, user_id: str, result_status: str, result_message: str = "",
           details: dict = None, service: str = "decision_recommendation", workspace_id: str = "default"):
    """审计便捷函数"""
    try:
        from odap.infra.security.unified_audit import log_audit
        log_audit(
            action=action,
            resource="decision_recommendation",
            user=user_id,
            service=service,
            result_status=result_status,
            result_message=result_message,
            details=details or {},
            workspace_id=workspace_id,
        )
    except Exception:
        pass


class RecommendRequest(BaseModel):
    simulation_results: Dict[str, Any]
    analysis_result: Optional[Dict[str, Any]] = None
    available_options: List[Dict[str, Any]] = Field(default_factory=list)
    constraints: Dict[str, Any] = Field(default_factory=dict)
    context: Dict[str, Any] = Field(default_factory=dict)


class RiskAssessmentRequest(BaseModel):
    recommendation: Dict[str, Any]


class HistoryResponse(BaseModel):
    history: List[Dict[str, Any]] = Field(default_factory=list)
    total: int = 0


@router.post("/recommend")
async def generate_recommendation(request: RecommendRequest,
    user=Depends(get_current_user)):
    _uid = user.get("sub", "anonymous") if isinstance(user, dict) else "anonymous"
    try:
        engine = _get_engine()
        sim_results = request.simulation_results
        if request.analysis_result:
            sim_results["analysis_result"] = request.analysis_result
        if request.available_options:
            sim_results["available_options"] = request.available_options
        if request.constraints:
            sim_results["constraints"] = request.constraints
        if request.context:
            sim_results["context"] = request.context
        result = await engine.generate_recommendations(sim_results)
        _audit("decision_recommendation_generate", _uid, "success")
        return result
    except HTTPException:
        raise
    except Exception as e:
        _audit("decision_recommendation_generate_failed", _uid, "failure", str(e))
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/risk-assessment")
async def risk_assessment(request: RiskAssessmentRequest,
    user=Depends(get_current_user)):
    _uid = user.get("sub", "anonymous") if isinstance(user, dict) else "anonymous"
    try:
        engine = _get_engine()
        result = await engine.assess_risks(request.recommendation)
        _audit("decision_recommendation_risk_assessment", _uid, "success")
        return result
    except HTTPException:
        raise
    except Exception as e:
        _audit("decision_recommendation_risk_assessment_failed", _uid, "failure", str(e))
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/recommendations/{recommendation_id}/explain")
async def explain_recommendation(recommendation_id: str,
    user=Depends(get_current_user)):
    _uid = user.get("sub", "anonymous") if isinstance(user, dict) else "anonymous"
    try:
        engine = _get_engine()
        result = engine.explain_recommendation(recommendation_id)
        if not result.get("found", True):
            raise HTTPException(status_code=404, detail="推荐记录不存在")
        return result
    except HTTPException:
        raise
    except Exception as e:
        _audit("decision_recommendation_explain_failed", _uid, "failure", str(e), details={"recommendation_id": recommendation_id})
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/history", response_model=HistoryResponse)
async def get_history(
    ontology_id: Optional[str] = None,
    limit: int = 20,
    user=Depends(get_current_user)):
    _uid = user.get("sub", "anonymous") if isinstance(user, dict) else "anonymous"
    try:
        engine = _get_engine()
        history = engine.get_history(ontology_id=ontology_id, limit=limit)
        return HistoryResponse(history=history, total=len(history))
    except HTTPException:
        raise
    except Exception as e:
        _audit("decision_recommendation_get_history_failed", _uid, "failure", str(e))
        raise HTTPException(status_code=500, detail=str(e))
