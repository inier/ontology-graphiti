from typing import Dict, Any, List, Optional

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from odap.biz.simulation.feedback.collector import FeedbackCollector
from odap.biz.simulation.feedback.analyzer import FeedbackAnalyzer
from odap.biz.simulation.feedback.aggregator import FeedbackAggregator
from odap.biz.simulation.feedback.loop import FeedbackLoop, get_feedback_loop
from odap.biz.simulation.feedback.models import Feedback, FeedbackType, FeedbackSeverity


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


@router.post("/action", response_model=ActionFeedbackResponse)
async def submit_action_feedback(request: ActionFeedbackRequest):
    if not request.action_id:
        raise HTTPException(status_code=400, detail="action_id 不能为空")
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
    except Exception as e:
        raise HTTPException(status_code=503, detail=f"反馈服务不可用: {str(e)}")


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
    except Exception as e:
        raise HTTPException(status_code=503, detail=f"反馈服务不可用: {str(e)}")
