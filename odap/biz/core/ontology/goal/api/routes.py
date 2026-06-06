"""OntoFlow Goal - FastAPI 路由 (T426)

前缀: /api/ontology/goals

端点:
- POST   /                              创建 Goal
- GET    /                              列出 (query: workspace_id, status, page, page_size)
- GET    /{goal_id}                     获取详情
- PUT    /{goal_id}                     更新
- DELETE /{goal_id}                     删除
- POST   /{goal_id}/transition          状态机转换
- POST   /{goal_id}/propose-change      创建 ChangeProposal + ImpactAnalysis
- GET    /{goal_id}/proposals           列出该 Goal 的所有 Proposal
- GET    /{goal_id}/lineage             获取 Goal 血缘
- POST   /proposals/{proposal_id}/review  审批 Proposal
"""
from __future__ import annotations

from typing import Optional

from fastapi import APIRouter, HTTPException, Query

from ..services import GoalService
from .schemas import (
    CreateGoalRequest,
    GoalResponse,
    GoalLineageResponse,
    ImpactResponse,
    ListGoalsResponse,
    ListProposalsResponse,
    ProposeChangeRequest,
    ProposeChangeResponse,
    ProposalResponse,
    ReviewProposalRequest,
    StatusTransitionRequest,
    UpdateGoalRequest,
)


router = APIRouter(
    prefix="/api/ontology/goals", tags=["ontology-goals"]
)

# 模块级单例
goal_service = GoalService()


@router.post("", response_model=GoalResponse, status_code=201)
async def create_goal(request: CreateGoalRequest):
    """创建 Goal"""
    try:
        result = await goal_service.create_goal(
            title=request.title,
            description=request.description,
            business_objective=request.business_objective,
            workspace_id=request.workspace_id,
            created_by=request.created_by,
            parent_goal_id=request.parent_goal_id,
            tags=request.tags,
            metadata=request.metadata,
            auto_rationale=request.auto_rationale,
        )
        if result.get("status") == "error":
            status_code = 400
            if "not found" in result["message"]:
                status_code = 404
            raise HTTPException(
                status_code=status_code, detail=result["message"]
            )
        return result
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("", response_model=ListGoalsResponse)
async def list_goals(
    workspace_id: str = Query(..., description="按 workspace_id 过滤"),
    status: Optional[str] = Query(None, description="按 status 过滤"),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=200),
):
    """列出 Goal"""
    try:
        result = goal_service.list_goals(
            workspace_id=workspace_id,
            status=status,
            page=page,
            page_size=page_size,
        )
        if result.get("status") == "error":
            raise HTTPException(status_code=400, detail=result["message"])
        return result
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/{goal_id}", response_model=GoalResponse)
async def get_goal(goal_id: str):
    """获取单条 Goal"""
    try:
        result = goal_service.get_goal(goal_id)
        if result.get("status") == "error":
            raise HTTPException(status_code=404, detail=result["message"])
        return result
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.put("/{goal_id}", response_model=GoalResponse)
async def update_goal(goal_id: str, request: UpdateGoalRequest):
    """更新 Goal（部分字段）"""
    try:
        payload = {k: v for k, v in request.model_dump().items() if v is not None}
        result = goal_service.update_goal(goal_id, payload)
        if result.get("status") == "error":
            status_code = 404 if "not found" in result["message"] else 400
            raise HTTPException(
                status_code=status_code, detail=result["message"]
            )
        return result
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.delete("/{goal_id}")
async def delete_goal(goal_id: str):
    """删除 Goal"""
    try:
        result = goal_service.delete_goal(goal_id)
        if result.get("status") == "error":
            raise HTTPException(status_code=404, detail=result["message"])
        return result
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/{goal_id}/transition", response_model=GoalResponse)
async def transition_goal(goal_id: str, request: StatusTransitionRequest):
    """状态机转换 (body: {"new_status": "approved"})"""
    try:
        result = goal_service.change_status(goal_id, request.new_status)
        if result.get("status") == "error":
            msg = result["message"]
            if "not found" in msg:
                status_code = 404
            elif "invalid" in msg:
                status_code = 400
            else:
                status_code = 400
            raise HTTPException(status_code=status_code, detail=msg)
        return result
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post(
    "/{goal_id}/propose-change", response_model=ProposeChangeResponse,
    status_code=201,
)
async def propose_change(goal_id: str, request: ProposeChangeRequest):
    """创建 ChangeProposal + 自动运行 ImpactAnalyzer"""
    try:
        result = goal_service.propose_change(
            goal_id=goal_id,
            title=request.title,
            description=request.description,
            changes=request.changes,
            proposed_by=request.proposed_by,
            estimated_benefit=request.estimated_benefit,
            estimated_cost=request.estimated_cost,
        )
        if result.get("status") == "error":
            msg = result["message"]
            if "not found" in msg:
                status_code = 404
            else:
                status_code = 400
            raise HTTPException(status_code=status_code, detail=msg)
        return result
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get(
    "/{goal_id}/proposals", response_model=ListProposalsResponse
)
async def list_proposals(goal_id: str):
    """列出该 Goal 的所有 ChangeProposal"""
    try:
        result = goal_service.list_proposals(goal_id=goal_id)
        if result.get("status") == "error":
            raise HTTPException(status_code=400, detail=result["message"])
        return result
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/{goal_id}/lineage", response_model=GoalLineageResponse)
async def get_goal_lineage(goal_id: str):
    """获取 Goal 血缘（祖先 + 子 + 关联 Proposal）"""
    try:
        result = goal_service.get_goal_lineage(goal_id)
        if result.get("status") == "error":
            raise HTTPException(status_code=404, detail=result["message"])
        return result
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post(
    "/proposals/{proposal_id}/review", response_model=ProposalResponse
)
async def review_proposal(
    proposal_id: str, request: ReviewProposalRequest
):
    """审批 ChangeProposal"""
    try:
        result = goal_service.review_proposal(
            proposal_id=proposal_id,
            decision=request.decision,
            reviewer_notes=request.reviewer_notes,
        )
        if result.get("status") == "error":
            msg = result["message"]
            if "not found" in msg:
                status_code = 404
            else:
                status_code = 400
            raise HTTPException(status_code=status_code, detail=msg)
        return result
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
