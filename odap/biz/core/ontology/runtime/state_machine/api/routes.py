from fastapi import APIRouter, HTTPException
from .schemas import CreateStateMachineRequest, TransitionRequest, BindActionRequest
from ..services import StateMachineService

router = APIRouter(prefix="/api/ontology/state-machines", tags=["state-machine"])
service = StateMachineService.get_instance()


@router.post("")
async def create_state_machine(request: CreateStateMachineRequest):
    try:
        result = service.create_state_machine(**request.model_dump())
        if result.get("status") == "error":
            raise HTTPException(status_code=400, detail=result["message"])
        return result
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/{sm_id}")
async def get_state_machine(sm_id: str):
    result = service.get_state_machine(sm_id)
    if result.get("status") == "error":
        raise HTTPException(status_code=404, detail=result["message"])
    return result


@router.get("")
async def list_state_machines(scenario_id: str = None, is_active: bool = None):
    return service.list_state_machines(scenario_id, is_active)


@router.delete("/{sm_id}")
async def delete_state_machine(sm_id: str):
    result = service.delete_state_machine(sm_id)
    if result.get("status") == "error":
        raise HTTPException(status_code=404, detail=result["message"])
    return result


@router.post("/{sm_id}/transition")
async def transition(sm_id: str, request: TransitionRequest):
    try:
        result = service.transition(sm_id, request.object_id, request.action_type_id, request.context)
        if result.get("status") == "error":
            raise HTTPException(status_code=400, detail=result["message"])
        return result
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/{sm_id}/objects/{object_id}/state")
async def get_object_state(sm_id: str, object_id: str):
    result = service.get_object_state(sm_id, object_id)
    if result.get("status") == "error":
        raise HTTPException(status_code=404, detail=result["message"])
    return result


@router.post("/{sm_id}/objects/{object_id}/reset")
async def reset_object_state(sm_id: str, object_id: str):
    result = service.reset_object_state(sm_id, object_id)
    if result.get("status") == "error":
        raise HTTPException(status_code=404, detail=result["message"])
    return result


@router.post("/{sm_id}/bind-action")
async def bind_action_type(sm_id: str, request: BindActionRequest):
    try:
        result = service.bind_action_type(sm_id, request.action_type_id)
        if result.get("status") == "error":
            raise HTTPException(status_code=400, detail=result["message"])
        return result
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
