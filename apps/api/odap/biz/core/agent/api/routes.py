from fastapi import APIRouter, HTTPException, Depends
from odap.infra.security.jwt_auth import get_current_user
from odap.infra.security.audit_helper import audit as _audit_shared
from typing import Dict, Any
import asyncio
import logging

from .schemas import DispatchRequest, SwarmConfigRequest, OrchestrateRequest, CreateSessionRequest

router = APIRouter(prefix="/api/agent", tags=["agent"])

logger = logging.getLogger(__name__)

_swarm_instance = None
_orchestrator_instance = None


def _audit(action: str, user_id: str, result_status: str, result_message: str = "",
           details: dict = None, service: str = "agent", workspace_id: str = "default"):
    """Agent审计便捷函数 - 使用共享 helper"""
    _audit_shared(
        action=action,
        user=user_id,
        result_status=result_status,
        result_message=result_message,
        details=details,
        service=service,
        workspace_id=workspace_id,
        resource="agent",
    )


def _get_swarm():
    global _swarm_instance
    if _swarm_instance is not None:
        return _swarm_instance
    from odap.biz.core.agent.swarm_orchestrator import DomainSwarm
    _swarm_instance = DomainSwarm()
    return _swarm_instance


def _get_orchestrator():
    global _orchestrator_instance
    if _orchestrator_instance is not None:
        return _orchestrator_instance
    from odap.biz.core.agent.agent_orchestrator import AgentOrchestrator
    _orchestrator_instance = AgentOrchestrator()
    return _orchestrator_instance


@router.post("/dispatch")
async def dispatch_intent(request: DispatchRequest,
    user=Depends(get_current_user)) -> Dict[str, Any]:
    user_id = user.get("sub", "anonymous") if isinstance(user, dict) else "anonymous"
    ws_id = request.workspace_id or "default"
    try:
        swarm = _get_swarm()
        # 30s 超时保护
        try:
            result = await asyncio.wait_for(
                swarm.dispatch_intent(
                    intent=request.intent,
                    context=request.context,
                    workspace_id=request.workspace_id,
                ),
                timeout=30.0,
            )
        except asyncio.TimeoutError:
            logger.warning(f"Agent dispatch timed out for: {request.intent[:50]}")
            _audit("agent_dispatch", user_id, "failure",
                   result_message="Agent dispatch timed out",
                   details={"intent": request.intent[:100]},
                   workspace_id=ws_id)
            result = {
                "task_id": "timeout",
                "assigned_agent": "unknown",
                "confidence": 0.0,
                "status": "timeout",
                "message": "智能体调度超时，请稍后重试",
            }
            return result
        _audit("agent_dispatch", user_id, "success",
               result_message="Agent dispatch completed",
               details={"intent": request.intent[:100], "task_id": result.get("task_id", "")},
               workspace_id=ws_id)
        return result
    except HTTPException:
        raise
    except Exception as e:
        _audit("agent_dispatch_failed", user_id, "failure",
               result_message=f"Agent dispatch failed: {str(e)[:200]}",
               details={"intent": request.intent[:100], "error_type": type(e).__name__},
               workspace_id=ws_id)
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/tasks/{task_id}")
async def get_task_status(task_id: str,
    user=Depends(get_current_user)) -> Dict[str, Any]:
    user_id = user.get("sub", "anonymous") if isinstance(user, dict) else "anonymous"
    try:
        swarm = _get_swarm()
        result = await swarm.get_task_status(task_id)
        if result.get("status") == "error":
            raise HTTPException(status_code=404, detail=result.get("message"))
        _audit("agent_get_task", user_id, "success",
               result_message="Agent task status retrieved",
               details={"task_id": task_id})
        return result
    except HTTPException:
        raise
    except Exception as e:
        _audit("agent_get_task_failed", user_id, "failure",
               result_message=f"Agent get task failed: {str(e)[:200]}",
               details={"task_id": task_id, "error_type": type(e).__name__})
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/tasks/{task_id}/chain")
async def get_decision_chain(task_id: str,
    user=Depends(get_current_user)) -> Dict[str, Any]:
    user_id = user.get("sub", "anonymous") if isinstance(user, dict) else "anonymous"
    try:
        swarm = _get_swarm()
        result = await swarm.get_decision_chain(task_id)
        if result.get("status") == "error":
            raise HTTPException(status_code=404, detail=result.get("message"))
        _audit("agent_get_chain", user_id, "success",
               result_message="Agent decision chain retrieved",
               details={"task_id": task_id})
        return result
    except HTTPException:
        raise
    except Exception as e:
        _audit("agent_get_chain_failed", user_id, "failure",
               result_message=f"Agent get chain failed: {str(e)[:200]}",
               details={"task_id": task_id, "error_type": type(e).__name__})
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/swarm/configure")
async def configure_swarm(request: SwarmConfigRequest,
    user=Depends(get_current_user)) -> Dict[str, Any]:
    user_id = user.get("sub", "anonymous") if isinstance(user, dict) else "anonymous"
    try:
        swarm = _get_swarm()
        result = await swarm.configure_swarm(
            agent_roles=request.agent_roles,
            routing_rules=request.routing_rules,
        )
        _audit("agent_configure_swarm", user_id, "success",
               result_message="Agent swarm configured",
               details={"has_agent_roles": request.agent_roles is not None,
                         "has_routing_rules": request.routing_rules is not None})
        return result
    except HTTPException:
        raise
    except Exception as e:
        _audit("agent_configure_swarm_failed", user_id, "failure",
               result_message=f"Agent configure swarm failed: {str(e)[:200]}",
               details={"error_type": type(e).__name__})
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/orchestrate")
async def orchestrate(request: OrchestrateRequest,
    user=Depends(get_current_user)) -> Dict[str, Any]:
    """统一 Agent 编排入口，根据 mode 自动分派到对应的 Agent Loop"""
    user_id = user.get("sub", "anonymous") if isinstance(user, dict) else "anonymous"
    ws_id = request.workspace_id or "default"
    try:
        orchestrator = _get_orchestrator()
        # 60s 超时保护（编排可能涉及多步推理和 LLM 调用）
        try:
            result = await asyncio.wait_for(
                orchestrator.dispatch(
                    query=request.query,
                    user_id=request.user_id,
                    workspace_id=request.workspace_id,
                    scenario_id=request.scenario_id,
                    agent_id=request.agent_id,
                    mode=request.mode,
                    session_id=request.session_id,
                ),
                timeout=60.0,
            )
        except asyncio.TimeoutError:
            logger.warning(f"Agent orchestrate timed out for: {request.query[:50]}")
            _audit("agent_orchestrate", user_id, "failure",
                   result_message="Agent orchestrate timed out",
                   details={"query": request.query[:100], "mode": request.mode},
                   workspace_id=ws_id)
            result = {
                "result_id": "timeout",
                "mode": request.mode,
                "answer": "",
                "reasoning_chain": [],
                "sources": [],
                "metadata": {"requested_mode": request.mode},
                "error": "智能体编排超时，请稍后重试",
            }

        # 持久化聊天历史到 SessionMemoryService
        if request.session_id:
            try:
                from odap.biz.platform.session_memory.services.session_memory_service import get_session_memory_service
                sms = get_session_memory_service()

                # 保存用户消息
                sms.add_message(
                    session_id=request.session_id,
                    role="user",
                    content=request.query,
                    tokens=0,
                    entities=[],
                )

                # 保存助手响应
                answer = result.get("answer", "")
                sms.add_message(
                    session_id=request.session_id,
                    role="assistant",
                    content=answer,
                    tokens=0,
                    entities=[],
                )

                result["session_id"] = request.session_id
            except Exception as e:
                logger.warning(f"Failed to save session messages: {e}")

        _audit("agent_orchestrate", user_id, "success",
               result_message="Agent orchestrate completed",
               details={"query": request.query[:100], "mode": request.mode,
                         "agent_id": request.agent_id or "default",
                         "result_id": result.get("result_id", "")},
               workspace_id=ws_id)
        return result
    except HTTPException:
        raise
    except Exception as e:
        # 审计：Agent 编排失败
        try:
            from odap.infra.security.unified_audit import log_audit
            log_audit(
                action="agent_orchestrate_failed",
                resource=f"agent:{request.agent_id or 'default'}",
                user=request.user_id,
                service="agent",
                result_status="failure",
                result_message=f"Agent orchestrate failed: {str(e)[:200]}",
                details={"query": request.query[:100], "mode": request.mode, "error_type": type(e).__name__},
                workspace_id=request.workspace_id or "default",
            )
        except Exception:
            pass
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/orchestrate/availability")
async def get_availability(
    user=Depends(get_current_user)) -> Dict[str, Any]:
    """查询各 Agent Loop 的可用状态"""
    user_id = user.get("sub", "anonymous") if isinstance(user, dict) else "anonymous"
    try:
        orchestrator = _get_orchestrator()
        availability = orchestrator.get_availability()
        _audit("agent_get_availability", user_id, "success",
               result_message="Agent availability retrieved",
               details={"availability": availability})
        return {"status": "ok", "availability": availability}
    except HTTPException:
        raise
    except Exception as e:
        _audit("agent_get_availability_failed", user_id, "failure",
               result_message=f"Agent get availability failed: {str(e)[:200]}",
               details={"error_type": type(e).__name__})
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/sessions")
async def create_agent_session(request: CreateSessionRequest,
    user=Depends(get_current_user)) -> Dict[str, Any]:
    """创建 Agent 会话"""
    user_id = user.get("sub", "anonymous") if isinstance(user, dict) else "anonymous"
    ws_id = request.workspace_id or "default"
    try:
        from odap.biz.platform.session_memory.services.session_memory_service import get_session_memory_service
        sms = get_session_memory_service()
        result = sms.create_session(
            workspace_id=request.workspace_id,
            title=request.title,
            max_tokens=8000,
        )
        _audit("agent_create_session", user_id, "success",
               result_message="Agent session created",
               details={"workspace_id": ws_id, "title": request.title},
               workspace_id=ws_id)
        return result
    except HTTPException:
        raise
    except Exception as e:
        _audit("agent_create_session_failed", user_id, "failure",
               result_message=f"Agent create session failed: {str(e)[:200]}",
               details={"workspace_id": ws_id, "error_type": type(e).__name__},
               workspace_id=ws_id)
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/sessions/{session_id}/messages")
async def get_session_messages(session_id: str,
    user=Depends(get_current_user)) -> Dict[str, Any]:
    """获取会话消息历史"""
    user_id = user.get("sub", "anonymous") if isinstance(user, dict) else "anonymous"
    try:
        from odap.biz.platform.session_memory.services.session_memory_service import get_session_memory_service
        sms = get_session_memory_service()
        context = sms.get_context(session_id)
        if not context:
            raise HTTPException(status_code=404, detail="Session not found")
        _audit("agent_get_messages", user_id, "success",
               result_message="Agent session messages retrieved",
               details={"session_id": session_id})
        return context
    except HTTPException:
        raise
    except Exception as e:
        _audit("agent_get_messages_failed", user_id, "failure",
               result_message=f"Agent get messages failed: {str(e)[:200]}",
               details={"session_id": session_id, "error_type": type(e).__name__})
        raise HTTPException(status_code=500, detail=str(e))
