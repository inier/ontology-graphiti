from fastapi import APIRouter, HTTPException
from typing import Dict, Any

from .schemas import DispatchRequest, SwarmConfigRequest

router = APIRouter(prefix="/api/agent", tags=["agent"])


def _get_swarm():
    from odap.biz.core.agent.swarm_orchestrator import DomainSwarm
    return DomainSwarm()


@router.post("/dispatch")
async def dispatch_intent(request: DispatchRequest) -> Dict[str, Any]:
    try:
        swarm = _get_swarm()
        result = await swarm.dispatch_intent(
            intent=request.intent,
            context=request.context,
            workspace_id=request.workspace_id,
        )
        return result
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/tasks/{task_id}")
async def get_task_status(task_id: str) -> Dict[str, Any]:
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
async def get_decision_chain(task_id: str) -> Dict[str, Any]:
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
async def configure_swarm(request: SwarmConfigRequest) -> Dict[str, Any]:
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
