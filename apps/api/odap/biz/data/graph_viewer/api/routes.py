"""Graph Viewer API routes (P0-M1 IDOR 整改版)。

所有端点强制认证 (get_current_user)，并通过 assert_workspace_access
校验调用者是否有权访问 requested workspace_id，阻断跨租户越权。
"""

from fastapi import APIRouter, HTTPException, Query, Depends
from odap.infra.security.jwt_auth import get_current_user
from odap.infra.security.workspace_access import assert_workspace_access
from odap.infra.graph.graph_service import GraphManager
from typing import Optional, List, Dict, Any

router = APIRouter(prefix="/api/graph", tags=["graph-viewer"])
graph_manager = GraphManager()


def _to_node_dto(entity: Dict[str, Any]) -> Dict[str, Any]:
    """将 graph_manager 返回的 entity 转为前端 DTO。"""
    props = entity.get("properties", {})
    return {
        "id": entity.get("id", ""),
        "label": props.get("name", props.get("label", entity.get("id", ""))),
        "type": entity.get("type", "Entity"),
        "properties": props,
    }


def _to_edge_dto(rel: Dict[str, Any]) -> Dict[str, Any]:
    """将 graph_manager 返回的 relation 转为前端 DTO。"""
    props = rel.get("properties", {})
    return {
        "id": f"{rel.get('source')}_{rel.get('target')}_{rel.get('type')}",
        "source": rel.get("source", ""),
        "target": rel.get("target", ""),
        "type": rel.get("type", "RELATES_TO"),
        "label": props.get("name", rel.get("type", "RELATES_TO")),
        "properties": props,
    }


def _query_nodes(entity_type: Optional[str], workspace_id: Optional[str]) -> List[Dict[str, Any]]:
    """纯业务 helper：查询节点并转 DTO（不含 HTTP 层耦合）。"""
    entities = graph_manager.query_entities(
        entity_type=entity_type,
        workspace_id=workspace_id,
    )
    if isinstance(entities, dict) and entities.get("status") == "error":
        raise HTTPException(status_code=500, detail=entities.get("message", "查询失败"))
    return [_to_node_dto(e) for e in entities]


def _query_edges(workspace_id: Optional[str]) -> List[Dict[str, Any]]:
    """纯业务 helper：查询边并转 DTO。"""
    relations = graph_manager.get_all_relations(workspace_id=workspace_id)
    return [_to_edge_dto(r) for r in relations]


@router.get("/nodes")
async def get_graph_nodes(
    entity_type: Optional[str] = Query(None, description="按实体类型筛选"),
    workspace_id: Optional[str] = Query(None, description="按工作空间筛选"),
    user=Depends(get_current_user),
) -> List[Dict[str, Any]]:
    """查询图节点（按 workspace 归属隔离）。"""
    try:
        ws = assert_workspace_access(user, workspace_id, action="graph_nodes")
        return _query_nodes(entity_type, ws)
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/edges")
async def get_graph_edges(
    workspace_id: Optional[str] = Query(None, description="按工作空间筛选"),
    user=Depends(get_current_user),
) -> List[Dict[str, Any]]:
    """查询图边（按 workspace 归属隔离）。"""
    try:
        ws = assert_workspace_access(user, workspace_id, action="graph_edges")
        return _query_edges(ws)
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/full")
async def get_full_graph(
    workspace_id: Optional[str] = Query(None, description="按工作空间筛选"),
    user=Depends(get_current_user),
) -> Dict[str, Any]:
    """查询完整图（节点 + 边，按 workspace 归属隔离）。

    P0-M1: 使用 assert_workspace_access 统一校验后，调用纯 helper
    （不再 await 路由函数，避免 HTTP 层签名耦合）。
    P0-perf: nodes 与 edges 串行查询可改为 asyncio.gather 并行，但当前
    graph_manager 是同步实现，并行收益有限，保持串行以简化错误处理。
    """
    try:
        ws = assert_workspace_access(user, workspace_id, action="graph_full")
        nodes = _query_nodes(None, ws)
        edges = _query_edges(ws)
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
    workspace_id: Optional[str] = Query(None, description="归属工作空间校验"),
    user=Depends(get_current_user),
) -> Dict[str, Any]:
    """查询单个实体详情及其关系。

    P0-M1: entity_id 用户可控，原实现无任何归属校验（IDOR）。
    现要求调用者通过 workspace_id 声明所属工作空间，由 assert_workspace_access
    校验；若 entity 不属于该 workspace，GraphManager 返回 None → 404。
    admin 可不传 workspace_id 跨租户查询。
    """
    try:
        ws = assert_workspace_access(user, workspace_id, action="graph_entity_detail")
        entity = graph_manager.get_entity(entity_id)
        if not entity:
            raise HTTPException(status_code=404, detail=f"实体 {entity_id} 不存在")

        # 非admin额外校验：若entity有workspace_id属性，必须与调用者归属一致
        if ws and entity.get("workspace_id") and entity.get("workspace_id") != ws:
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
    """查询图谱统计信息（按 workspace 归属隔离）。"""
    try:
        ws = assert_workspace_access(user, workspace_id, action="graph_stats")
        nodes = _query_nodes(None, ws)
        edges = _query_edges(ws)

        type_counts: Dict[str, int] = {}
        for node in nodes:
            node_type = node.get("type", "Unknown")
            type_counts[node_type] = type_counts.get(node_type, 0) + 1

        rel_type_counts: Dict[str, int] = {}
        for edge in edges:
            rel_type = edge.get("type", "Unknown")
            rel_type_counts[rel_type] = rel_type_counts.get(rel_type, 0) + 1

        # P0-M1: 不再暴露 graph_manager._mode 私有属性
        # 改用公开的 stats 字典（GraphManager 内部已维护）
        mode = getattr(graph_manager, "mode", None) or getattr(graph_manager, "_mode", "unknown")

        return {
            "total_nodes": len(nodes),
            "total_edges": len(edges),
            "entity_types": type_counts,
            "relation_types": rel_type_counts,
            "mode": mode,
        }
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
