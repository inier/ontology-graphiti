from fastapi import APIRouter, HTTPException
from .memory_graph_sync import MemoryGraphSyncService

router = APIRouter(prefix="/api/ontology-memory/sync", tags=["memory-graph-sync"])
service = MemoryGraphSyncService.get_instance()


@router.post("/memory/{memory_id}/to-graph")
async def sync_memory_to_graph(memory_id: str):
    try:
        result = service.sync_memory_to_graph(memory_id)
        if result.get("status") == "error":
            raise HTTPException(status_code=500, detail=result["message"])
        return result
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/graph/to-memory")
async def sync_graph_to_memory(scenario_id: str = None, limit: int = 50):
    try:
        return service.sync_graph_to_memory(scenario_id, limit)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/consolidated")
async def on_consolidated(request: dict):
    try:
        return service.on_memory_consolidated(
            request.get("source_ids", []), request.get("result_id", ""))
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/decayed")
async def on_decayed(request: dict):
    try:
        return service.on_memory_decayed(request.get("decayed_ids", []))
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/forgotten")
async def on_forgotten(request: dict):
    try:
        return service.on_memory_forgotten(
            request.get("forgotten_ids", []), request.get("archived", False))
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/memory/{memory_id}/status")
async def get_sync_status(memory_id: str):
    return service.get_sync_status(memory_id)


@router.get("/unsynced")
async def list_unsynced(limit: int = 100):
    return service.list_unsynced(limit)
