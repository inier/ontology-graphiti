from fastapi import APIRouter, HTTPException, Query
from .schemas import CreateSnapshotRequest, AddDimensionNodeRequest, LinkDimensionsRequest
from ..services import get_abution_graph_service

router = APIRouter(prefix="/api/ontology/abution-graph", tags=["ontology-abution-graph"])


@router.post("", response_model=dict)
async def create_snapshot(request: CreateSnapshotRequest):
    try:
        service = get_abution_graph_service()
        result = service.create_snapshot(
            name=request.name,
            temporal_nodes=[n.model_dump() for n in request.temporal_nodes],
            pattern_nodes=[n.model_dump() for n in request.pattern_nodes],
            force_nodes=[n.model_dump() for n in request.force_nodes],
            action_nodes=[n.model_dump() for n in request.action_nodes],
            cross_dimension_links=request.cross_dimension_links,
        )
        if result.get("status") == "error":
            raise HTTPException(status_code=400, detail=result["message"])
        return result
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("", response_model=dict)
async def list_snapshots(limit: int = Query(100, ge=1, le=1000)):
    try:
        service = get_abution_graph_service()
        return service.list_snapshots(limit=limit)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/{snapshot_id}", response_model=dict)
async def get_snapshot(snapshot_id: str):
    try:
        service = get_abution_graph_service()
        result = service.get_snapshot(snapshot_id)
        if result.get("status") == "error":
            raise HTTPException(status_code=404, detail=result["message"])
        return result
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.delete("/{snapshot_id}", response_model=dict)
async def delete_snapshot(snapshot_id: str):
    try:
        service = get_abution_graph_service()
        result = service.delete_snapshot(snapshot_id)
        if result.get("status") == "error":
            raise HTTPException(status_code=404, detail=result["message"])
        return result
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/{snapshot_id}/nodes", response_model=dict)
async def add_dimension_node(snapshot_id: str, request: AddDimensionNodeRequest):
    try:
        service = get_abution_graph_service()
        result = service.add_dimension_node(
            snapshot_id=snapshot_id,
            dimension=request.dimension,
            node_data=request.node_data,
        )
        if result.get("status") == "error":
            raise HTTPException(status_code=400, detail=result["message"])
        return result
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/{snapshot_id}/links", response_model=dict)
async def link_dimensions(snapshot_id: str, request: LinkDimensionsRequest):
    try:
        service = get_abution_graph_service()
        result = service.link_dimensions(
            snapshot_id=snapshot_id,
            source_dim=request.source_dim,
            source_id=request.source_id,
            target_dim=request.target_dim,
            target_id=request.target_id,
            link_type=request.link_type,
        )
        if result.get("status") == "error":
            raise HTTPException(status_code=400, detail=result["message"])
        return result
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/{snapshot_id}/analyze", response_model=dict)
async def analyze_cross_dimension_patterns(snapshot_id: str):
    try:
        service = get_abution_graph_service()
        result = service.analyze_cross_dimension_patterns(snapshot_id)
        if result.get("status") == "error":
            raise HTTPException(status_code=404, detail=result["message"])
        return result
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
