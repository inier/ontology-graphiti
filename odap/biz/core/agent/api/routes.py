from fastapi import APIRouter, HTTPException, Depends
from odap.infra.security.jwt_auth import get_current_user
from typing import Dict, Any
import asyncio
import logging

from .schemas import DispatchRequest, SwarmConfigRequest, OrchestrateRequest, CreateSessionRequest

router = APIRouter(prefix="/api/agent", tags=["agent"])

logger = logging.getLogger(__name__)

_swarm_instance = None
_orchestrator_instance = None


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
            result = {
                "task_id": "timeout",
                "assigned_agent": "unknown",
                "confidence": 0.0,
                "status": "timeout",
                "message": "智能体调度超时，请稍后重试",
            }
        return result
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/tasks/{task_id}")
async def get_task_status(task_id: str,
    user=Depends(get_current_user)) -> Dict[str, Any]:
    try:
        swarm = _get_swarm()
        result = await swarm.get_task_status(task_id)
        if result.get("status") == "error":
            raise HTTPException(status_code=404, detail=result.get("message"))
        return result
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/tasks/{task_id}/chain")
async def get_decision_chain(task_id: str,
    user=Depends(get_current_user)) -> Dict[str, Any]:
    try:
        swarm = _get_swarm()
        result = await swarm.get_decision_chain(task_id)
        if result.get("status") == "error":
            raise HTTPException(status_code=404, detail=result.get("message"))
        return result
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/swarm/configure")
async def configure_swarm(request: SwarmConfigRequest,
    user=Depends(get_current_user)) -> Dict[str, Any]:
    try:
        swarm = _get_swarm()
        result = await swarm.configure_swarm(
            agent_roles=request.agent_roles,
            routing_rules=request.routing_rules,
        )
        return result
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/orchestrate")
async def orchestrate(request: OrchestrateRequest,
    user=Depends(get_current_user)) -> Dict[str, Any]:
    """统一 Agent 编排入口，根据 mode 自动分派到对应的 Agent Loop"""
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

        return result
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/orchestrate/availability")
async def get_availability(
    user=Depends(get_current_user)) -> Dict[str, Any]:
    """查询各 Agent Loop 的可用状态"""
    try:
        orchestrator = _get_orchestrator()
        availability = orchestrator.get_availability()
        return {"status": "ok", "availability": availability}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/sessions")
async def create_agent_session(request: CreateSessionRequest,
    user=Depends(get_current_user)) -> Dict[str, Any]:
    """创建 Agent 会话"""
    try:
        from odap.biz.platform.session_memory.services.session_memory_service import get_session_memory_service
        sms = get_session_memory_service()
        result = sms.create_session(
            workspace_id=request.workspace_id,
            title=request.title,
            max_tokens=8000,
        )
        return result
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/sessions/{session_id}/messages")
async def get_session_messages(session_id: str,
    user=Depends(get_current_user)) -> Dict[str, Any]:
    """获取会话消息历史"""
    try:
        from odap.biz.platform.session_memory.services.session_memory_service import get_session_memory_service
        sms = get_session_memory_service()
        context = sms.get_context(session_id)
        if not context:
            raise HTTPException(status_code=404, detail="Session not found")
        return context
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
