from fastapi import APIRouter, HTTPException
from ..services.thought_graph_service import ThoughtGraphService

router = APIRouter(prefix="/api/thoughts", tags=["thought-graph"])
service = ThoughtGraphService.get_instance()


@router.post("")
async def add_thought(request: dict):
    try:
        result = service.add_thought(**request)
        if result.get("status") == "error":
            raise HTTPException(status_code=400, detail=result["message"])
        return result
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/{thought_id}")
async def get_thought(thought_id: str):
    result = service.get_thought(thought_id)
    if result.get("status") == "error":
        raise HTTPException(status_code=404, detail=result["message"])
    return result


@router.get("")
async def list_thoughts(thought_type: str = None, scenario_id: str = None,
                        agent_id: str = None, limit: int = 100):
    return service.list_thoughts(thought_type, scenario_id, agent_id, limit)


@router.delete("/{thought_id}")
async def delete_thought(thought_id: str):
    result = service.delete_thought(thought_id)
    if result.get("status") == "error":
        raise HTTPException(status_code=404, detail=result["message"])
    return result


@router.post("/chains")
async def create_chain(request: dict):
    try:
        result = service.create_reasoning_chain(**request)
        if result.get("status") == "error":
            raise HTTPException(status_code=400, detail=result["message"])
        return result
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/chains/{chain_id}")
async def get_chain(chain_id: str):
    result = service.get_chain(chain_id)
    if result.get("status") == "error":
        raise HTTPException(status_code=404, detail=result["message"])
    return result


@router.get("/chains")
async def list_chains(scenario_id: str = None, limit: int = 100):
    return service.list_chains(scenario_id, limit)


@router.delete("/chains/{chain_id}")
async def delete_chain(chain_id: str):
    result = service.delete_chain(chain_id)
    if result.get("status") == "error":
        raise HTTPException(status_code=404, detail=result["message"])
    return result


@router.post("/link")
async def link_thoughts(request: dict):
    try:
        return service.link_thoughts(**request)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/{thought_id}/graph")
async def get_thought_graph(thought_id: str, depth: int = 2):
    return service.get_thought_graph(thought_id, depth)


@router.post("/{thought_id}/sync-graphiti")
async def sync_to_graphiti(thought_id: str):
    result = service.sync_to_graphiti(thought_id)
    if result.get("status") == "error":
        raise HTTPException(status_code=500, detail=result["message"])
    return result
