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
        return result
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/risk-assessment")
async def risk_assessment(request: RiskAssessmentRequest,
    user=Depends(get_current_user)):
    try:
        engine = _get_engine()
        result = await engine.assess_risks(request.recommendation)
        return result
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/recommendations/{recommendation_id}/explain")
async def explain_recommendation(recommendation_id: str,
    user=Depends(get_current_user)):
    try:
        engine = _get_engine()
        result = engine.explain_recommendation(recommendation_id)
        if not result.get("found", True):
            raise HTTPException(status_code=404, detail="推荐记录不存在")
        return result
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/history", response_model=HistoryResponse)
async def get_history(
    ontology_id: Optional[str] = None,
    limit: int = 20,
    user=Depends(get_current_user)):
    try:
        engine = _get_engine()
        history = engine.get_history(ontology_id=ontology_id, limit=limit)
        return HistoryResponse(history=history, total=len(history))
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
