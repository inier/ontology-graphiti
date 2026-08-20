from fastapi import APIRouter, HTTPException, Depends
from odap.infra.security.jwt_auth import get_current_user
from odap.infra.security.workspace_access import assert_workspace_access
from typing import Optional

from .schemas import AnalysisInput, PipelineResult
from .pipeline import get_decision_pipeline

router = APIRouter(prefix="/api/decision-pipeline", tags=["decision-pipeline"])


@router.post("/execute", response_model=PipelineResult)
async def execute_pipeline(input_data: AnalysisInput,
    user=Depends(get_current_user)):
    # ADR-076 §7：workspace_id 路由层解析（JWT 声明覆盖客户端透传，缺失 → 422）
    input_data.workspace_id = assert_workspace_access(user, input_data.workspace_id)
    pipeline = get_decision_pipeline()
    try:
        return await pipeline.execute(input_data)
    except ValueError as e:
        raise HTTPException(status_code=422, detail=str(e))


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


@router.get("/progress")
async def pipeline_progress(
    pipeline_id: str = "",
    workspace_id: str = "",
    user=Depends(get_current_user)):
    """ADR-064 增补：流水线进度可观测查询（按 workspace 过滤）。

    安全要求：workspace_id 从 JWT 声明解析，覆盖客户端透传。
    """
    # 解析工作空间（JWT 声明覆盖；空则默认用户 workspace）
    resolved_ws = workspace_id
    if resolved_ws:
        resolved_ws = assert_workspace_access(user, resolved_ws)
    else:
        resolved_ws = getattr(user, "workspace_id", "") or ""

    pipeline = get_decision_pipeline()
    return pipeline.get_pipeline_progress(
        pipeline_id=pipeline_id,
        workspace_id=resolved_ws,
    )
