"""前端API兼容层 - Agent调度/决策/反馈路由

1:1 重复原生 /api/agent/ 的端点已删除，前端应直接调用:
  GET  /api/agent/tools       — 列出工具
  POST /api/agent/run          — 运行 Agent
  GET  /api/agent/status       — 健康状态

反馈端点已修正为代理到原生 FeedbackLoop（而非仅写审计日志），前端也可直接调用:
  POST /api/feedback/action             — 提交动作反馈
  GET  /api/feedback/decision/{id}      — 获取决策反馈
"""

from fastapi import APIRouter, HTTPException, Request, Depends
from odap.infra.security.jwt_auth import get_current_user
from typing import Dict, Any
import logging

logger = logging.getLogger(__name__)

def _fca_audit(action: str, *, result_status: str = "success",
               result_message: str = "", resource: str = None,
               details: Dict[str, Any] = None) -> None:
    try:
        from odap.infra.security.audit_helper import storage_audit
        storage_audit(action=action, result_status=result_status,
                      result_message=result_message, resource=resource,
                      details=details or {}, service="integration_frontend_compat")
    except Exception as e:
        logger.warning(f"audit failed: {e}")


router = APIRouter(prefix="/api/compat", tags=["frontend-compat-agent"])


# ==================== OpenHarness 独有能力（原生 /api/agent/ 无此功能） ====================

@router.post("/openharness/run-episode")
async def run_openharness_episode(data: Dict[str, Any],
    user=Depends(get_current_user)):
    try:
        from odap.infra.openharness import create_harness
        harness = create_harness()
        if not harness:
            raise HTTPException(status_code=503, detail="OpenHarness 不可用")

        actions = data.get("actions", [])
        if not isinstance(actions, list):
            raise HTTPException(status_code=400, detail="actions 必须是数组")

        results = harness.run_episode(actions)
        _fca_audit(
            action="frontend_compat_openharness_run_episode",
            result_status="success",
            resource="openharness_episode",
            details={
                "actions_count": len(actions),
                "total_steps": len(results),
                "item_count": len(actions),
            },
        )
        return {
            "results": results,
            "total_steps": len(results),
            "done": results[-1]["done"] if results else False,
        }
    except HTTPException as he:
        _fca_audit(
            action="frontend_compat_openharness_run_episode",
            result_status="failure",
            result_message=str(he.detail)[:200],
            resource="openharness_episode",
            details={"actions_count": len(data.get("actions", []))},
        )
        raise
    except Exception as e:
        _fca_audit(
            action="frontend_compat_openharness_run_episode",
            result_status="failure",
            result_message=str(e)[:200],
            resource="openharness_episode",
            details={},
        )
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/openharness/health")
async def check_openharness_health():
    try:
        from odap.infra.openharness import create_harness
        harness = create_harness()
        if harness:
            tools = harness.list_available_tools()
            return {
                "status": "healthy",
                "openharness_available": True,
                "tools_count": len(tools),
                "tools": tools[:5],
            }
        return {
            "status": "healthy",
            "openharness_available": False,
            "message": "OpenHarness 不可用，使用 fallback 模式",
        }
    except HTTPException:
        raise
    except Exception as e:
        return {
            "status": "unhealthy",
            "openharness_available": False,
            "error": str(e),
        }


@router.get("/openharness/schemas")
async def get_openharness_schemas(user=Depends(get_current_user)):
    try:
        from odap.infra.openharness import export_tool_schemas
        schemas = export_tool_schemas()
        return {
            "schemas": schemas,
            "count": len(schemas),
        }
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# ==================== 闭环反馈路由（代理到原生 FeedbackLoop） ====================

@router.post("/feedback/action")
async def submit_action_feedback(request: Request, data: Dict[str, Any],
    user=Depends(get_current_user)):
    """
    提交动作执行反馈 — 代理到原生 FeedbackLoop

    请求体:
    {
        "action_id": "动作ID",
        "decision_id": "关联的决策ID",
        "outcome": "success|failure|partial",
        "result_data": {},
        "error_message": "错误信息（如果失败）"
    }
    """
    try:
        action_id = data.get("action_id", "")
        data.get("decision_id")
        outcome = data.get("outcome", "success")
        result_data = data.get("result_data", {})
        error_message = data.get("error_message")

        if not action_id:
            raise HTTPException(status_code=400, detail="action_id 不能为空")

        from odap.biz.simulation.feedback.loop import get_feedback_loop
        feedback_loop = get_feedback_loop()
        feedback = feedback_loop.collector.collect_action_result(
            action_id=action_id,
            outcome=outcome,
            result_data=result_data,
            error_message=error_message,
        )
        loop_result = feedback_loop.close_loop(feedback)

        _fca_audit(
            action="frontend_compat_feedback_action",
            result_status="success",
            resource=feedback.id,
            details={
                "feedback_id": feedback.id,
                "outcome": outcome,
                "deviation_score": feedback.deviation_score,
                "graph_updated": loop_result.get("graph_updated", False),
                "item_count": 1,
            },
        )

        return {
            "status": "success",
            "feedback_id": feedback.id,
            "outcome": outcome,
            "deviation_score": feedback.deviation_score,
            "lesson_learned": loop_result.get("lesson_learned", ""),
            "graph_updated": loop_result.get("graph_updated", False),
            "episode_created": loop_result.get("episode_created", False),
            "hook_emitted": loop_result.get("hook_emitted", False),
        }
    except HTTPException as he:
        _fca_audit(
            action="frontend_compat_feedback_action",
            result_status="failure",
            result_message=str(he.detail)[:200],
            resource="",
            details={"action_id": data.get("action_id", "")},
        )
        raise
    except Exception as e:
        _fca_audit(
            action="frontend_compat_feedback_action",
            result_status="failure",
            result_message=str(e)[:200],
            resource="",
            details={},
        )
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/feedback/decision/{decision_id}")
async def get_decision_feedback(decision_id: str,
    user=Depends(get_current_user)):
    try:
        from odap.biz.simulation.feedback.loop import get_feedback_loop
        feedback_loop = get_feedback_loop()
        feedbacks = feedback_loop.get_feedback_history(decision_id)

        return {
            "decision_id": decision_id,
            "feedback_count": len(feedbacks),
            "feedbacks": [
                {
                    "feedback_id": fb.id,
                    "outcome": fb.feedback_type.value,
                    "severity": fb.severity.value,
                    "deviation_score": fb.deviation_score,
                    "lesson_learned": fb.lesson_learned,
                    "timestamp": fb.timestamp.isoformat() if hasattr(fb, 'timestamp') else "",
                }
                for fb in feedbacks
            ],
        }
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
