from fastapi import APIRouter, HTTPException, Depends
from odap.infra.security.jwt_auth import get_current_user
from typing import Optional

from .schemas import AnalysisInput, PipelineResult
from .pipeline import get_decision_pipeline

router = APIRouter(prefix="/api/decision-pipeline", tags=["decision-pipeline"])


@router.post("/execute", response_model=PipelineResult)
async def execute_pipeline(input_data: AnalysisInput,
    user=Depends(get_current_user)):
    pipeline = get_decision_pipeline()
    return await pipeline.execute(input_data)


@router.post("/analyze")
async def analyze_only(input_data: AnalysisInput,
    user=Depends(get_current_user)):
    pipeline = get_decision_pipeline()
    analysis = await pipeline._analyze(input_data)
    return analysis


@router.post("/decide")
async def decide_only(input_data: AnalysisInput,
    user=Depends(get_current_user)):
    pipeline = get_decision_pipeline()
    analysis = await pipeline._analyze(input_data)
    decision = await pipeline._decide(analysis, input_data)
    return decision
