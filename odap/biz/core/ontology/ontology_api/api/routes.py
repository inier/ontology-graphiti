"""Ontology API 路由层

遵循 AGENTS.md 规则：
- 路由前缀统一 /api/ontologies
- except HTTPException: raise 必须透传
- 服务层返回 Dict，路由层翻译错误为 HTTPException
"""
from fastapi import APIRouter, HTTPException, Query, Depends
from odap.infra.security.jwt_auth import get_current_user
from typing import Optional

from ..services import OntologyService

router = APIRouter(prefix="/api/ontologies", tags=["ontology-api"])
service = OntologyService()


# ===== Ontology CRUD =====
@router.get("")
async def list_ontologies(
    workspace_id: Optional[str] = Query(None),
    user=Depends(get_current_user),
):
    try:
        return service.list_ontologies(workspace_id=workspace_id)
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/{ontology_id}")
async def get_ontology(ontology_id: str, user=Depends(get_current_user)):
    try:
        result = service.get_ontology(ontology_id)
        if result.get("status") == "error":
            raise HTTPException(status_code=404, detail=result.get("message"))
        return result
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("")
async def create_ontology(data: dict, user=Depends(get_current_user)):
    try:
        result = service.create_ontology(
            name=data.get("name", ""),
            description=data.get("description", ""),
            workspace_id=data.get("workspace_id", ""),
            scenario_id=data.get("scenario_id"),
        )
        if result.get("status") == "error":
            raise HTTPException(status_code=400, detail=result.get("message"))
        return result
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.put("/{ontology_id}")
async def update_ontology(ontology_id: str, data: dict, user=Depends(get_current_user)):
    try:
        result = service.update_ontology(ontology_id, data)
        if result.get("status") == "error":
            raise HTTPException(status_code=404, detail=result.get("message"))
        return result
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.delete("/{ontology_id}")
async def delete_ontology(ontology_id: str, user=Depends(get_current_user)):
    try:
        result = service.delete_ontology(ontology_id)
        if result.get("status") == "error":
            raise HTTPException(status_code=404, detail=result.get("message"))
        return result
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# ===== Schema Version Management =====
@router.post("/{ontology_id}/commit")
async def commit_schema_version(ontology_id: str, data: dict, user=Depends(get_current_user)):
    try:
        result = service.commit_schema_version(
            ontology_id=ontology_id,
            changelog=data.get("changelog", ""),
        )
        if result.get("status") == "error":
            raise HTTPException(status_code=400, detail=result.get("message"))
        return result
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/{ontology_id}/versions")
async def list_schema_versions(ontology_id: str, user=Depends(get_current_user)):
    try:
        return service.list_schema_versions(ontology_id)
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/{ontology_id}/diff")
async def diff_schema_versions(
    ontology_id: str,
    version_id_a: str = Query(...),
    version_id_b: str = Query(...),
    user=Depends(get_current_user),
):
    try:
        result = service.diff_schema_versions(ontology_id, version_id_a, version_id_b)
        if result.get("status") == "error":
            raise HTTPException(status_code=400, detail=result.get("message"))
        return result
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/{ontology_id}/rollback")
async def rollback_schema_version(ontology_id: str, data: dict, user=Depends(get_current_user)):
    try:
        result = service.rollback_schema_version(
            ontology_id=ontology_id,
            target_version_id=data.get("target_version_id", ""),
        )
        if result.get("status") == "error":
            raise HTTPException(status_code=400, detail=result.get("message"))
        return result
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# ===== ObjectType CRUD =====
@router.get("/{ontology_id}/object-types")
async def list_object_types(ontology_id: str, user=Depends(get_current_user)):
    try:
        return service.list_object_types(ontology_id)
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/{ontology_id}/object-types")
async def create_object_type(ontology_id: str, data: dict, user=Depends(get_current_user)):
    try:
        result = service.create_object_type(ontology_id, data)
        if result.get("status") == "error":
            raise HTTPException(status_code=400, detail=result.get("message"))
        return result
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.put("/object-types/{type_id}")
async def update_object_type(type_id: str, data: dict, user=Depends(get_current_user)):
    try:
        result = service.update_object_type(type_id, data)
        if result.get("status") == "error":
            raise HTTPException(status_code=404, detail=result.get("message"))
        return result
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.delete("/object-types/{type_id}")
async def delete_object_type(type_id: str, user=Depends(get_current_user)):
    try:
        result = service.delete_object_type(type_id)
        if result.get("status") == "error":
            raise HTTPException(status_code=404, detail=result.get("message"))
        return result
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# ===== LinkType CRUD =====
@router.get("/{ontology_id}/link-types")
async def list_link_types(ontology_id: str, user=Depends(get_current_user)):
    try:
        return service.list_link_types(ontology_id)
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/{ontology_id}/link-types")
async def create_link_type(ontology_id: str, data: dict, user=Depends(get_current_user)):
    try:
        result = service.create_link_type(ontology_id, data)
        if result.get("status") == "error":
            raise HTTPException(status_code=400, detail=result.get("message"))
        return result
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.put("/link-types/{link_id}")
async def update_link_type(link_id: str, data: dict, user=Depends(get_current_user)):
    try:
        result = service.update_link_type(link_id, data)
        if result.get("status") == "error":
            raise HTTPException(status_code=404, detail=result.get("message"))
        return result
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.delete("/link-types/{link_id}")
async def delete_link_type(link_id: str, user=Depends(get_current_user)):
    try:
        result = service.delete_link_type(link_id)
        if result.get("status") == "error":
            raise HTTPException(status_code=404, detail=result.get("message"))
        return result
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# ===== ActionType CRUD =====
@router.get("/{ontology_id}/action-types")
async def list_action_types(ontology_id: str, user=Depends(get_current_user)):
    try:
        return service.list_action_types(ontology_id)
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/{ontology_id}/action-types")
async def create_action_type(ontology_id: str, data: dict, user=Depends(get_current_user)):
    try:
        result = service.create_action_type(ontology_id, data)
        if result.get("status") == "error":
            raise HTTPException(status_code=400, detail=result.get("message"))
        return result
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.put("/action-types/{action_type_id}")
async def update_action_type(action_type_id: str, data: dict, user=Depends(get_current_user)):
    try:
        result = service.update_action_type(action_type_id, data)
        if result.get("status") == "error":
            raise HTTPException(status_code=404, detail=result.get("message"))
        return result
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.delete("/action-types/{action_type_id}")
async def delete_action_type(action_type_id: str, user=Depends(get_current_user)):
    try:
        result = service.delete_action_type(action_type_id)
        if result.get("status") == "error":
            raise HTTPException(status_code=404, detail=result.get("message"))
        return result
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# ===== ProcessType CRUD =====
@router.get("/{ontology_id}/process-types")
async def list_process_types(ontology_id: str, user=Depends(get_current_user)):
    try:
        return service.list_process_types(ontology_id)
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/{ontology_id}/process-types")
async def create_process_type(ontology_id: str, data: dict, user=Depends(get_current_user)):
    try:
        result = service.create_process_type(ontology_id, data)
        if result.get("status") == "error":
            raise HTTPException(status_code=400, detail=result.get("message"))
        return result
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.put("/process-types/{type_id}")
async def update_process_type(type_id: str, data: dict, user=Depends(get_current_user)):
    try:
        result = service.update_process_type(type_id, data)
        if result.get("status") == "error":
            raise HTTPException(status_code=404, detail=result.get("message"))
        return result
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.delete("/process-types/{type_id}")
async def delete_process_type(type_id: str, user=Depends(get_current_user)):
    try:
        result = service.delete_process_type(type_id)
        if result.get("status") == "error":
            raise HTTPException(status_code=404, detail=result.get("message"))
        return result
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# ===== RuleType CRUD =====
@router.get("/{ontology_id}/rule-types")
async def list_rule_types(ontology_id: str, user=Depends(get_current_user)):
    try:
        return service.list_rule_types(ontology_id)
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/{ontology_id}/rule-types")
async def create_rule_type(ontology_id: str, data: dict, user=Depends(get_current_user)):
    try:
        result = service.create_rule_type(ontology_id, data)
        if result.get("status") == "error":
            raise HTTPException(status_code=400, detail=result.get("message"))
        return result
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.put("/rule-types/{type_id}")
async def update_rule_type(type_id: str, data: dict, user=Depends(get_current_user)):
    try:
        result = service.update_rule_type(type_id, data)
        if result.get("status") == "error":
            raise HTTPException(status_code=404, detail=result.get("message"))
        return result
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.delete("/rule-types/{type_id}")
async def delete_rule_type(type_id: str, user=Depends(get_current_user)):
    try:
        result = service.delete_rule_type(type_id)
        if result.get("status") == "error":
            raise HTTPException(status_code=404, detail=result.get("message"))
        return result
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# ===== FunctionType CRUD =====
@router.get("/{ontology_id}/function-types")
async def list_function_types(ontology_id: str, user=Depends(get_current_user)):
    try:
        return service.list_function_types(ontology_id)
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/{ontology_id}/function-types")
async def create_function_type(ontology_id: str, data: dict, user=Depends(get_current_user)):
    try:
        result = service.create_function_type(ontology_id, data)
        if result.get("status") == "error":
            raise HTTPException(status_code=400, detail=result.get("message"))
        return result
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.put("/function-types/{type_id}")
async def update_function_type(type_id: str, data: dict, user=Depends(get_current_user)):
    try:
        result = service.update_function_type(type_id, data)
        if result.get("status") == "error":
            raise HTTPException(status_code=404, detail=result.get("message"))
        return result
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.delete("/function-types/{type_id}")
async def delete_function_type(type_id: str, user=Depends(get_current_user)):
    try:
        result = service.delete_function_type(type_id)
        if result.get("status") == "error":
            raise HTTPException(status_code=404, detail=result.get("message"))
        return result
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# ===== IndicatorType CRUD =====
@router.get("/{ontology_id}/indicator-types")
async def list_indicator_types(ontology_id: str, user=Depends(get_current_user)):
    try:
        return service.list_indicator_types(ontology_id)
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/{ontology_id}/indicator-types")
async def create_indicator_type(ontology_id: str, data: dict, user=Depends(get_current_user)):
    try:
        result = service.create_indicator_type(ontology_id, data)
        if result.get("status") == "error":
            raise HTTPException(status_code=400, detail=result.get("message"))
        return result
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.put("/indicator-types/{type_id}")
async def update_indicator_type(type_id: str, data: dict, user=Depends(get_current_user)):
    try:
        result = service.update_indicator_type(type_id, data)
        if result.get("status") == "error":
            raise HTTPException(status_code=404, detail=result.get("message"))
        return result
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.delete("/indicator-types/{type_id}")
async def delete_indicator_type(type_id: str, user=Depends(get_current_user)):
    try:
        result = service.delete_indicator_type(type_id)
        if result.get("status") == "error":
            raise HTTPException(status_code=404, detail=result.get("message"))
        return result
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# ===== Graph Data =====
@router.get("/{ontology_id}/graph")
async def get_ontology_graph(ontology_id: str, user=Depends(get_current_user)):
    try:
        result = service.get_ontology_graph(ontology_id)
        if result.get("status") == "error":
            raise HTTPException(status_code=400, detail=result.get("message"))
        return result
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# ===== Database Connection =====
@router.get("/database-connections")
async def list_database_connections(
    workspace_id: str = Query(...),
    user=Depends(get_current_user),
):
    try:
        return service.list_database_connections(workspace_id)
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/database-connections")
async def save_database_connection(data: dict, user=Depends(get_current_user)):
    try:
        result = service.save_database_connection(data)
        if result.get("status") == "error":
            raise HTTPException(status_code=400, detail=result.get("message"))
        return result
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.delete("/database-connections/{connection_id}")
async def delete_database_connection(connection_id: str, user=Depends(get_current_user)):
    try:
        result = service.delete_database_connection(connection_id)
        if result.get("status") == "error":
            raise HTTPException(status_code=404, detail=result.get("message"))
        return result
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# ===== Extraction Session =====
@router.post("/{ontology_id}/extraction-sessions")
async def create_extraction_session(ontology_id: str, data: dict, user=Depends(get_current_user)):
    try:
        result = service.create_extraction_session(
            ontology_id=ontology_id,
            extraction_type=data.get("extraction_type", ""),
            input_data=data.get("input_data", {}),
        )
        if result.get("status") == "error":
            raise HTTPException(status_code=400, detail=result.get("message"))
        return result
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/extraction-sessions/{session_id}")
async def get_extraction_session(session_id: str, user=Depends(get_current_user)):
    try:
        result = service.get_extraction_session(session_id)
        if result.get("status") == "error":
            raise HTTPException(status_code=404, detail=result.get("message"))
        return result
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.put("/extraction-sessions/{session_id}")
async def update_extraction_session(session_id: str, data: dict, user=Depends(get_current_user)):
    try:
        result = service.update_extraction_session(session_id, data)
        if result.get("status") == "error":
            raise HTTPException(status_code=404, detail=result.get("message"))
        return result
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
