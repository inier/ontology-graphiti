from fastapi import APIRouter, HTTPException, Depends
from odap.infra.security.jwt_auth import get_current_user
from .shared_memory_service import SharedMemoryService

router = APIRouter(prefix="/api/ontology-memory/shared", tags=["shared-memory"])
service = SharedMemoryService.get_instance()


@router.post("/contexts")
async def create_context(request: dict,
    user=Depends(get_current_user)):
    try:
        result = service.create_context(
            name=request.get("name", ""),
            description=request.get("description", ""),
            scenario_id=request.get("scenario_id"),
            session_id=request.get("session_id"),
            initial_state=request.get("initial_state")
        )
        if result.get("status") == "error":
            raise HTTPException(status_code=400, detail=result["message"])
        return result
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/contexts/{context_id}")
async def get_context(context_id: str,
    user=Depends(get_current_user)):
    result = service.get_context(context_id)
    if result.get("status") == "error":
        raise HTTPException(status_code=404, detail=result["message"])
    return result


@router.get("/contexts")
async def list_contexts(scenario_id: str = None, is_active: bool = None,
    user=Depends(get_current_user)):
    return service.list_contexts(scenario_id, is_active)


@router.delete("/contexts/{context_id}")
async def delete_context(context_id: str,
    user=Depends(get_current_user)):
    result = service.delete_context(context_id)
    if result.get("status") == "error":
        raise HTTPException(status_code=404, detail=result["message"])
    return result


@router.post("/contexts/{context_id}/state")
async def update_shared_state(context_id: str, request: dict,
    user=Depends(get_current_user)):
    try:
        result = service.update_shared_state(context_id, request.get("agent_id", ""),
                                             request.get("updates", {}))
        if result.get("status") == "error":
            raise HTTPException(status_code=400, detail=result["message"])
        return result
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/contexts/{context_id}/state")
async def read_shared_state(context_id: str, keys: str = None,
    user=Depends(get_current_user)):
    key_list = keys.split(",") if keys else None
    return service.read_shared_state(context_id, key_list)


@router.post("/contexts/{context_id}/join")
async def join_context(context_id: str, request: dict,
    user=Depends(get_current_user)):
    try:
        return service.join_context(context_id, request.get("agent_id", ""),
                                    request.get("agent_role", ""))
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/contexts/{context_id}/leave")
async def leave_context(context_id: str, request: dict,
    user=Depends(get_current_user)):
    try:
        return service.leave_context(context_id, request.get("agent_id", ""))
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/contexts/{context_id}/heartbeat")
async def heartbeat(context_id: str, request: dict,
    user=Depends(get_current_user)):
    try:
        return service.heartbeat(context_id, request.get("agent_id", ""),
                                 request.get("state_data"))
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/contexts/{context_id}/agents")
async def get_agent_states(context_id: str,
    user=Depends(get_current_user)):
    return service.get_agent_states(context_id)


@router.get("/contexts/{context_id}/events")
async def get_pending_events(context_id: str, agent_id: str = None, limit: int = 100,
    user=Depends(get_current_user)):
    return service.get_pending_events(context_id, agent_id, limit)


@router.post("/events/{event_id}/consume")
async def consume_event(event_id: str,
    user=Depends(get_current_user)):
    result = service.consume_event(event_id)
    if result.get("status") == "error":
        raise HTTPException(status_code=404, detail=result["message"])
    return result


@router.post("/contexts/{context_id}/consensus")
async def request_consensus(context_id: str, request: dict,
    user=Depends(get_current_user)):
    try:
        return service.request_consensus(context_id, request.get("agent_id", ""),
                                         request.get("topic", ""), request.get("proposal", ""))
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/contexts/{context_id}/vote")
async def vote_consensus(context_id: str, request: dict,
    user=Depends(get_current_user)):
    try:
        return service.vote_consensus(context_id, request.get("agent_id", ""),
                                      request.get("topic", ""), request.get("vote", ""),
                                      request.get("reason", ""))
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
