from fastapi import APIRouter, HTTPException, Query
from typing import Optional

from .blueprint_service import BlueprintDesignerService
from .api.schemas import (
    CreateBlueprintRequest,
    UpdateBlueprintRequest,
    AddNodeRequest,
    UpdateNodeRequest,
    AddEdgeRequest,
    BatchAddNodesRequest,
    BatchAddEdgesRequest,
    BatchUpdatePositionsRequest,
    ImportBlueprintRequest,
)

router = APIRouter(prefix="/api/ontology/blueprints", tags=["blueprint-designer"])
service = BlueprintDesignerService.get_instance()


@router.post("", response_model=dict)
async def create_blueprint(request: CreateBlueprintRequest):
    try:
        result = service.create_blueprint(
            name=request.name, description=request.description,
            scenario_id=request.scenario_id, nodes=request.nodes,
            edges=request.edges, layout=request.layout, metadata=request.metadata,
        )
        if result.get("status") == "error":
            raise HTTPException(status_code=400, detail=result["message"])
        return result
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/{blueprint_id}", response_model=dict)
async def get_blueprint(blueprint_id: str):
    result = service.get_blueprint(blueprint_id)
    if result.get("status") == "error":
        raise HTTPException(status_code=404, detail=result["message"])
    return result


@router.get("", response_model=dict)
async def list_blueprints(
    scenario_id: Optional[str] = Query(None),
    is_published: Optional[bool] = Query(None),
    limit: int = Query(100),
):
    return service.list_blueprints(scenario_id, is_published, limit)


@router.put("/{blueprint_id}", response_model=dict)
async def update_blueprint(blueprint_id: str, request: UpdateBlueprintRequest):
    try:
        updates = {k: v for k, v in request.model_dump().items() if v is not None}
        result = service.update_blueprint(blueprint_id, **updates)
        if result.get("status") == "error":
            raise HTTPException(status_code=400, detail=result["message"])
        return result
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.delete("/{blueprint_id}", response_model=dict)
async def delete_blueprint(blueprint_id: str):
    result = service.delete_blueprint(blueprint_id)
    if result.get("status") == "error":
        raise HTTPException(status_code=404, detail=result["message"])
    return result


@router.post("/{blueprint_id}/nodes", response_model=dict)
async def add_node(blueprint_id: str, request: AddNodeRequest):
    try:
        result = service.add_node(blueprint_id, request.node_type, request.name,
                                  request.position, request.config)
        if result.get("status") == "error":
            raise HTTPException(status_code=400, detail=result["message"])
        return result
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.put("/{blueprint_id}/nodes/{node_id}", response_model=dict)
async def update_node(blueprint_id: str, node_id: str, request: UpdateNodeRequest):
    try:
        updates = {k: v for k, v in request.model_dump().items() if v is not None}
        result = service.update_node(blueprint_id, node_id, **updates)
        if result.get("status") == "error":
            raise HTTPException(status_code=404, detail=result["message"])
        return result
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.delete("/{blueprint_id}/nodes/{node_id}", response_model=dict)
async def remove_node(blueprint_id: str, node_id: str):
    result = service.remove_node(blueprint_id, node_id)
    if result.get("status") == "error":
        raise HTTPException(status_code=404, detail=result["message"])
    return result


@router.post("/{blueprint_id}/edges", response_model=dict)
async def add_edge(blueprint_id: str, request: AddEdgeRequest):
    try:
        result = service.add_edge(blueprint_id, request.source, request.target,
                                  request.edge_type, request.label)
        if result.get("status") == "error":
            raise HTTPException(status_code=400, detail=result["message"])
        return result
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.delete("/{blueprint_id}/edges/{edge_id}", response_model=dict)
async def remove_edge(blueprint_id: str, edge_id: str):
    result = service.remove_edge(blueprint_id, edge_id)
    if result.get("status") == "error":
        raise HTTPException(status_code=404, detail=result["message"])
    return result


@router.post("/{blueprint_id}/nodes/batch", response_model=dict)
async def batch_add_nodes(blueprint_id: str, request: BatchAddNodesRequest):
    try:
        nodes = [n.model_dump() for n in request.nodes]
        result = service.batch_add_nodes(blueprint_id, nodes)
        if result.get("status") == "error":
            raise HTTPException(status_code=400, detail=result["message"])
        return result
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/{blueprint_id}/edges/batch", response_model=dict)
async def batch_add_edges(blueprint_id: str, request: BatchAddEdgesRequest):
    try:
        edges = [e.model_dump() for e in request.edges]
        result = service.batch_add_edges(blueprint_id, edges)
        if result.get("status") == "error":
            raise HTTPException(status_code=400, detail=result["message"])
        return result
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.put("/{blueprint_id}/positions", response_model=dict)
async def batch_update_positions(blueprint_id: str, request: BatchUpdatePositionsRequest):
    try:
        result = service.batch_update_positions(blueprint_id, request.positions)
        if result.get("status") == "error":
            raise HTTPException(status_code=400, detail=result["message"])
        return result
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/{blueprint_id}/auto-layout", response_model=dict)
async def auto_layout(blueprint_id: str,
                      direction: str = Query("TB"),
                      spacing_x: int = Query(250),
                      spacing_y: int = Query(100)):
    try:
        result = service.auto_layout(blueprint_id, direction, spacing_x, spacing_y)
        if result.get("status") == "error":
            raise HTTPException(status_code=400, detail=result["message"])
        return result
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/import", response_model=dict)
async def import_blueprint(request: ImportBlueprintRequest):
    try:
        result = service.import_blueprint(request.name, request.data, request.scenario_id)
        if result.get("status") == "error":
            raise HTTPException(status_code=400, detail=result["message"])
        return result
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/{blueprint_id}/pipeline-config", response_model=dict)
async def export_pipeline_config(blueprint_id: str):
    result = service.export_to_pipeline_config(blueprint_id)
    if result.get("status") == "error":
        raise HTTPException(status_code=404, detail=result["message"])
    return result


@router.post("/{blueprint_id}/validate", response_model=dict)
async def validate_blueprint(blueprint_id: str):
    return service.validate_blueprint(blueprint_id)


@router.post("/{blueprint_id}/publish", response_model=dict)
async def publish_blueprint(blueprint_id: str):
    try:
        result = service.publish_blueprint(blueprint_id)
        if result.get("status") == "error":
            raise HTTPException(status_code=400, detail=result["message"])
        return result
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/{blueprint_id}/fork", response_model=dict)
async def fork_blueprint(blueprint_id: str, request: dict = None):
    try:
        return service.fork_blueprint(blueprint_id, (request or {}).get("new_name"))
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/{blueprint_id}/export", response_model=dict)
async def export_blueprint(blueprint_id: str, format: str = Query("json")):
    result = service.export_blueprint(blueprint_id, format)
    if result.get("status") == "error":
        raise HTTPException(status_code=400, detail=result["message"])
    return result


@router.get("/{blueprint_id}/version-history", response_model=dict)
async def get_version_history(blueprint_id: str):
    result = service.get_version_history(blueprint_id)
    if result.get("status") == "error":
        raise HTTPException(status_code=404, detail=result["message"])
    return result
