from fastapi import APIRouter, HTTPException, Query, Depends
from odap.infra.security.jwt_auth import get_current_user
from odap.infra.graph.graph_service import GraphManager
from typing import Optional, List, Dict, Any

router = APIRouter(prefix="/api/graph", tags=["graph-viewer"])
graph_manager = GraphManager()


@router.get("/nodes")
async def get_graph_nodes(
    entity_type: Optional[str] = Query(None, description="按实体类型筛选"),
    workspace_id: Optional[str] = Query(None, description="按工作空间筛选"),
    user=Depends(get_current_user),
) -> List[Dict[str, Any]]:
    try:
        entities = graph_manager.query_entities(
            entity_type=entity_type,
            workspace_id=workspace_id,
        )
        if isinstance(entities, dict) and entities.get("status") == "error":
            raise HTTPException(status_code=500, detail=entities.get("message", "查询失败"))

        result = []
        for entity in entities:
            props = entity.get("properties", {})
            result.append({
                "id": entity.get("id", ""),
                "label": props.get("name", props.get("label", entity.get("id", ""))),
                "type": entity.get("type", "Entity"),
                "properties": props,
            })
        return result
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/edges")
async def get_graph_edges(
    workspace_id: Optional[str] = Query(None, description="按工作空间筛选"),
    user=Depends(get_current_user),
) -> List[Dict[str, Any]]:
    try:
        relations = graph_manager.get_all_relations(workspace_id=workspace_id)
        result = []
        for rel in relations:
            props = rel.get("properties", {})
            result.append({
                "id": f"{rel.get('source')}_{rel.get('target')}_{rel.get('type')}",
                "source": rel.get("source", ""),
                "target": rel.get("target", ""),
                "type": rel.get("type", "RELATES_TO"),
                "label": props.get("name", rel.get("type", "RELATES_TO")),
                "properties": props,
            })
        return result
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/full")
async def get_full_graph(
    workspace_id: Optional[str] = Query(None, description="按工作空间筛选"),
    user=Depends(get_current_user),
) -> Dict[str, Any]:
    try:
        nodes = await get_graph_nodes(workspace_id=workspace_id, user=user)
        edges = await get_graph_edges(workspace_id=workspace_id, user=user)
        return {
            "nodes": nodes,
            "edges": edges,
            "node_count": len(nodes),
            "edge_count": len(edges),
        }
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/entity/{entity_id}")
async def get_entity_details(
    entity_id: str,
    user=Depends(get_current_user),
) -> Dict[str, Any]:
    try:
        entity = graph_manager.get_entity(entity_id)
        if not entity:
            raise HTTPException(status_code=404, detail=f"实体 {entity_id} 不存在")

        relations = graph_manager.get_entity_relations(entity_id)
        props = entity.get("properties", {})

        return {
            "id": entity.get("id", ""),
            "label": props.get("name", props.get("label", entity.get("id", ""))),
            "type": entity.get("type", "Entity"),
            "properties": props,
            "relations": relations,
            "relation_count": len(relations),
        }
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/stats")
async def get_graph_stats(
    workspace_id: Optional[str] = Query(None, description="按工作空间筛选"),
    user=Depends(get_current_user),
) -> Dict[str, Any]:
    try:
        nodes = await get_graph_nodes(workspace_id=workspace_id, user=user)
        edges = await get_graph_edges(workspace_id=workspace_id, user=user)

        type_counts: Dict[str, int] = {}
        for node in nodes:
            node_type = node.get("type", "Unknown")
            type_counts[node_type] = type_counts.get(node_type, 0) + 1

        rel_type_counts: Dict[str, int] = {}
        for edge in edges:
            rel_type = edge.get("type", "Unknown")
            rel_type_counts[rel_type] = rel_type_counts.get(rel_type, 0) + 1

        return {
            "total_nodes": len(nodes),
            "total_edges": len(edges),
            "entity_types": type_counts,
            "relation_types": rel_type_counts,
            "mode": graph_manager._mode,
        }
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))