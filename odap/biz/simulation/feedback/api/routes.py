from typing import Dict, Any, List, Optional

from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel, Field

from odap.biz.simulation.feedback.loop import FeedbackLoop, get_feedback_loop
from odap.biz.simulation.feedback.models import Feedback, FeedbackType, FeedbackSeverity


class CollectFeedbackRequest(BaseModel):
    source_id: str
    feedback_type: str = "action_result"
    outcome: str = "success"
    data: Dict[str, Any] = Field(default_factory=dict)


class CloseLoopRequest(BaseModel):
    source_id: str
    feedback_type: str = "action_result"
    outcome: str = "success"
    data: Dict[str, Any] = Field(default_factory=dict)


class ActionFeedbackRequest(BaseModel):
    action_id: str
    decision_id: Optional[str] = None
    outcome: str = "success"
    result_data: Dict[str, Any] = Field(default_factory=dict)
    error_message: Optional[str] = None


class ActionFeedbackResponse(BaseModel):
    status: str
    feedback_id: str
    outcome: str
    deviation_score: float = 0.0
    lesson_learned: str = ""
    graph_updated: bool = False
    episode_created: bool = False
    hook_emitted: bool = False


class DecisionFeedbackResponse(BaseModel):
    decision_id: str
    feedback_count: int = 0
    feedbacks: List[Dict[str, Any]] = Field(default_factory=list)


router = APIRouter(prefix="/api/feedback", tags=["feedback"])


@router.post("/collect")
async def collect_feedback(request: CollectFeedbackRequest):
    if not request.source_id:
        raise HTTPException(status_code=400, detail="source_id cannot be empty")
    try:
        feedback_loop = get_feedback_loop()
        feedback = feedback_loop.collect_feedback(
            source_id=request.source_id,
            feedback_type=request.feedback_type,
            data=request.data,
            outcome=request.outcome,
        )
        return {
            "status": "success",
            "feedback_id": feedback.id,
            "feedback_type": feedback.feedback_type.value,
            "severity": feedback.severity.value,
            "deviation_score": feedback.deviation_score,
        }
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=503, detail=f"Feedback service unavailable: {str(e)}")


@router.get("/analysis/{task_id}")
async def analyze_feedback(task_id: str):
    try:
        feedback_loop = get_feedback_loop()
        result = feedback_loop.analyze_feedback(task_id)
        if result.get("status") == "error":
            raise HTTPException(status_code=404, detail=result.get("message"))
        return result
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=503, detail=f"Feedback service unavailable: {str(e)}")


@router.get("/aggregate")
async def aggregate_feedback(ontology_id: str = Query(...)):
    try:
        feedback_loop = get_feedback_loop()
        return feedback_loop.aggregate_feedback(ontology_id)
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=503, detail=f"Feedback service unavailable: {str(e)}")


@router.post("/close-loop")
async def close_loop(request: CloseLoopRequest):
    if not request.source_id:
        raise HTTPException(status_code=400, detail="source_id cannot be empty")
    try:
        feedback_loop = get_feedback_loop()
        feedback = feedback_loop.collect_feedback(
            source_id=request.source_id,
            feedback_type=request.feedback_type,
            data=request.data,
            outcome=request.outcome,
        )
        result = feedback_loop.close_loop(feedback)
        return {
            "status": "success",
            "feedback_id": feedback.id,
            "lesson_learned": result.get("lesson_learned", ""),
            "graph_updated": result.get("graph_updated", False),
            "episode_created": result.get("episode_created", False),
            "hook_emitted": result.get("hook_emitted", False),
            "propagated": result.get("propagated", False),
            "propagate_targets": result.get("propagate_targets", []),
        }
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=503, detail=f"Feedback service unavailable: {str(e)}")


@router.post("/action", response_model=ActionFeedbackResponse)
async def submit_action_feedback(request: ActionFeedbackRequest):
    if not request.action_id:
        raise HTTPException(status_code=400, detail="action_id cannot be empty")
    try:
        feedback_loop = get_feedback_loop()
        feedback = feedback_loop.collector.collect_action_result(
            action_id=request.action_id,
            outcome=request.outcome,
            result_data=request.result_data,
            error_message=request.error_message,
        )
        loop_result = feedback_loop.close_loop(feedback)
        return ActionFeedbackResponse(
            status="success",
            feedback_id=feedback.id,
            outcome=request.outcome,
            deviation_score=feedback.deviation_score,
            lesson_learned=loop_result.get("lesson_learned", ""),
            graph_updated=loop_result.get("graph_updated", False),
            episode_created=loop_result.get("episode_created", False),
            hook_emitted=loop_result.get("hook_emitted", False),
        )
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=503, detail=f"Feedback service unavailable: {str(e)}")


@router.get("/decision/{decision_id}", response_model=DecisionFeedbackResponse)
async def get_decision_feedback(decision_id: str):
    try:
        feedback_loop = get_feedback_loop()
        feedbacks = feedback_loop.get_feedback_history(decision_id)
        feedback_list = []
        for fb in feedbacks:
            feedback_list.append({
                "feedback_id": fb.id,
                "feedback_type": fb.feedback_type.value,
                "severity": fb.severity.value,
                "title": fb.title,
                "description": fb.description,
                "deviation_score": fb.deviation_score,
                "deviation_factors": fb.deviation_factors,
                "root_causes": fb.root_causes,
                "lesson_learned": fb.lesson_learned,
                "timestamp": fb.timestamp.isoformat(),
            })
        return DecisionFeedbackResponse(
            decision_id=decision_id,
            feedback_count=len(feedback_list),
            feedbacks=feedback_list,
        )
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=503, detail=f"Feedback service unavailable: {str(e)}")
