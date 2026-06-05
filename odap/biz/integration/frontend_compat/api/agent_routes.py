"""前端API兼容层 - Agent调度/决策/反馈路由"""

from fastapi import APIRouter, HTTPException, Request, Depends
from odap.infra.security.jwt_auth import get_current_user
from typing import Dict, Any
import uuid
import asyncio
from datetime import datetime as dt

from odap.biz.integration.frontend_compat.api._deps import (
    audit_logger,
    AuditEventType,
    ActorInfo,
    ResourceInfo,
)

router = APIRouter(prefix="/api/compat", tags=["frontend-compat-agent"])


# ==================== OpenHarness 路由 ====================

@router.get("/openharness/tools")
async def list_openharness_tools(user=Depends(get_current_user)):
    """列出所有 OpenHarness 工具"""
    try:
        from odap.infra.openharness import create_harness
        harness = create_harness()
        if harness:
            tools = harness.list_available_tools()
            return {"tools": tools, "count": len(tools)}
        return {"tools": [], "count": 0, "message": "OpenHarness 不可用"}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/openharness/run")
async def run_openharness_action(data: Dict[str, Any],
    user=Depends(get_current_user)):
    """运行 OpenHarness 工具"""
    try:
        from odap.infra.openharness import create_harness
        harness = create_harness()
        if not harness:
            raise HTTPException(status_code=503, detail="OpenHarness 不可用")

        action = data.get("action")
        if not action:
            raise HTTPException(status_code=400, detail="action 不能为空")

        obs, reward, done, info = harness.step(action)
        return {
            "observation": obs,
            "reward": reward,
            "done": done,
            "info": info,
        }
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/openharness/run-episode")
async def run_openharness_episode(data: Dict[str, Any],
    user=Depends(get_current_user)):
    """运行完整的 OpenHarness 会话"""
    try:
        from odap.infra.openharness import create_harness
        harness = create_harness()
        if not harness:
            raise HTTPException(status_code=503, detail="OpenHarness 不可用")

        actions = data.get("actions", [])
        if not isinstance(actions, list):
            raise HTTPException(status_code=400, detail="actions 必须是数组")

        results = harness.run_episode(actions)
        return {
            "results": results,
            "total_steps": len(results),
            "done": results[-1]["done"] if results else False,
        }
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/openharness/health")
async def check_openharness_health():
    """检查 OpenHarness 健康状态"""
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
    """获取 OpenHarness 工具的 OpenAI 格式 schema"""
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


# ==================== 闭环反馈路由 ====================

@router.post("/feedback/action")
async def submit_action_feedback(request: Request, data: Dict[str, Any],
    user=Depends(get_current_user)):
    """
    提交动作执行反馈

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
        decision_id = data.get("decision_id")
        outcome = data.get("outcome", "success")
        result_data = data.get("result_data", {})
        error_message = data.get("error_message")

        asyncio.create_task(
            audit_logger.log_success(
                event_type=AuditEventType.DATA_INGEST,
                action="ACTION_FEEDBACK",
                resource=ResourceInfo(
                    resource_type="feedback",
                    resource_id=action_id,
                    resource_name="动作反馈",
                ),
                message=f"动作反馈: {outcome}",
                actor=ActorInfo(
                    actor_type="user",
                    actor_id=data.get("user_id", "system"),
                    actor_name=data.get("user_id", "System"),
                    roles=[],
                ),
                context={
                    "action_id": action_id,
                    "decision_id": decision_id,
                    "outcome": outcome,
                    "result_data": result_data,
                    "error_message": error_message,
                    "duration_ms": data.get("duration_ms", 0),
                },
            )
        )

        return {
            "status": "success",
            "feedback_id": f"af_{uuid.uuid4().hex[:12]}",
            "outcome": outcome,
        }
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/feedback/decision/{decision_id}")
async def get_decision_feedback(decision_id: str,
    user=Depends(get_current_user)):
    """获取决策的反馈历史"""
    try:
        from odap.biz.integration.frontend_compat.api._deps import AuditFilter

        audit_filter = AuditFilter(
            limit=100,
            order_by="timestamp",
            order_desc=True,
        )

        events = await audit_logger.query(audit_filter)

        feedback_events = [
            e for e in events
            if e.context and e.context.get("decision_id") == decision_id
        ]

        return {
            "decision_id": decision_id,
            "feedback_count": len(feedback_events),
            "feedbacks": [
                {
                    "feedback_id": e.id,
                    "outcome": e.context.get("outcome", "unknown"),
                    "timestamp": e.timestamp.isoformat() if isinstance(e.timestamp, dt) else str(e.timestamp),
                }
                for e in feedback_events
            ],
        }
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
