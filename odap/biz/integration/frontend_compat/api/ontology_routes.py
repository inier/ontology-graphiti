"""前端API兼容层 - 本体/图谱/查询/场景路由"""

from fastapi import APIRouter, HTTPException, Query, Request, Depends
from odap.infra.security.jwt_auth import get_current_user
from typing import Dict, Any, List, Optional
import json
import uuid
from datetime import datetime

from odap.biz.integration.frontend_compat.api._deps import (
    scenario_store,
    _get_graph_manager,
    audit_logger,
    AuditFilter,
    AuditEventType,
    local_audit_log,
    log_query,
    log_error,
)

router = APIRouter(prefix="/api/compat", tags=["frontend-compat-ontology"])


# ==================== 场景查询路由 ====================

@router.get("/scenarios/{scenario_id}/entities")
async def get_entities(scenario_id: str, workspace_id: str = None,
    user=Depends(get_current_user)):
    try:
        entities = scenario_store.get_entities(scenario_id)
        return {"scenario_id": scenario_id, "entities": entities, "count": len(entities)}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/scenarios/{scenario_id}/relations")
async def get_relations(scenario_id: str, workspace_id: str = None,
    user=Depends(get_current_user)):
    try:
        graph = scenario_store.get_relations(scenario_id)
        return {"scenario_id": scenario_id, **graph}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# ==================== 图谱查询路由 ====================

@router.post("/query/entities")
@local_audit_log(action="QUERY_ENTITIES", resource="entities")
async def query_entities(request: Request, data: Dict[str, Any],
    user=Depends(get_current_user)):
    """查询实体（兼容前端）"""
    try:
        query = data.get("query", {})
        workspace_id = data.get("workspace_id")

        graph_manager = _get_graph_manager()

        if query.get("keyword"):
            results = graph_manager.search(query.get("keyword"))
            entities = [
                {
                    "entity_id": r.get("id", r.get("name", "")),
                    "name": r.get("name", ""),
                    "type": r.get("type", ""),
                    "properties": r,
                }
                for r in results
            ]
        else:
            entities_raw = graph_manager.get_all_entities(workspace_id=workspace_id)
            entities = []
            for e in entities_raw:
                e_dict = e.to_dict() if hasattr(e, 'to_dict') else dict(e)
                props = e_dict.get("properties", {})
                eid = e_dict.get("id", "") or props.get("id", "")
                ename = props.get("name", "") or e_dict.get("name", "")
                etype = e_dict.get("type", e_dict.get("entity_type", "Entity"))
                if not eid or not ename:
                    continue
                if not props.get("source_type"):
                    props["source_type"] = "random"
                entities.append({
                    "entity_id": eid,
                    "name": ename,
                    "type": etype,
                    "properties": props,
                })

        log_query(query.get("keyword", ""), len(entities), user="system")

        return {
            "entities": entities,
            "total": len(entities),
        }
    except HTTPException:
        raise
    except Exception as e:
        log_error(str(e), context="query_entities")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/query/relations")
async def query_relations(data: Dict[str, Any],
    user=Depends(get_current_user)):
    """查询关系（兼容前端）"""
    try:
        query = data.get("query", {})
        source_id = query.get("source_id")
        target_id = query.get("target_id")
        relation_type = query.get("relation_type")
        workspace_id = data.get("workspace_id")

        graph_manager = _get_graph_manager()
        all_relations = graph_manager.get_all_relations(workspace_id=workspace_id)

        relations = []
        for r in all_relations:
            r_dict = r.to_dict() if hasattr(r, 'to_dict') else dict(r)
            if source_id and r_dict.get("source_entity", r_dict.get("source", "")) != source_id:
                continue
            if target_id and r_dict.get("target_entity", r_dict.get("target", "")) != target_id:
                continue
            if relation_type and r_dict.get("relation_type", r_dict.get("type", "")) != relation_type:
                continue
            relations.append({
                "relation_id": r_dict.get("relation_id", r_dict.get("id", "")),
                "source": r_dict.get("source_entity", r_dict.get("source", "")),
                "target": r_dict.get("target_entity", r_dict.get("target", "")),
                "type": r_dict.get("relation_type", r_dict.get("type", "")),
                "properties": r_dict.get("properties", {}),
            })

        return {
            "relations": relations,
            "total": len(relations),
        }
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/query/complex")
@local_audit_log(action="QUERY_COMPLEX", resource="complex")
async def complex_query(request: Request, data: Dict[str, Any],
    user=Depends(get_current_user)):
    """复合查询（兼容前端）"""
    try:
        conditions = data.get("conditions", [])
        workspace_id = data.get("workspace_id")

        graph_manager = _get_graph_manager()
        results = []
        for condition in conditions:
            if condition.get("type") == "entity":
                keyword = condition.get("value", "")
                if keyword:
                    search_results = graph_manager.search(keyword)
                    for r in search_results:
                        if r not in results:
                            results.append(r)

        entities = [
            {
                "entity_id": r.get("id", r.get("name", "")),
                "name": r.get("name", ""),
                "type": r.get("type", ""),
                "properties": r,
            }
            for r in results
        ]

        query_str = str(conditions)
        log_query(query_str, len(entities), user="system")

        return {
            "results": entities,
            "total": len(entities),
        }
    except HTTPException:
        raise
    except Exception as e:
        log_error(str(e), context="query_complex")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/query/history")
async def get_query_history(limit: int = Query(50, ge=1, le=200),
    user=Depends(get_current_user)):
    """获取查询历史（兼容前端）"""
    try:
        audit_filter = AuditFilter(
            limit=limit,
            order_by="timestamp",
            order_desc=True,
        )
        events = await audit_logger.query(audit_filter)
        query_events = [e for e in events if "QUERY" in e.action]

        history = []
        for e in query_events:
            history.append({
                "query_id": e.id,
                "action": e.action,
                "timestamp": e.timestamp.isoformat() if isinstance(e.timestamp, datetime) else str(e.timestamp),
                "actor": e.actor.actor_id if e.actor else "system",
                "context": e.context,
            })

        return {
            "history": history,
            "limit": limit,
        }
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/query/export")
async def export_query_results(data: Dict[str, Any],
    user=Depends(get_current_user)):
    """导出查询结果（兼容前端）"""
    try:
        results = data.get("results", [])
        export_format = data.get("format", "json")

        if export_format == "json":
            return {
                "success": True,
                "data": json.dumps(results, ensure_ascii=False, indent=2),
            }
        elif export_format == "csv":
            if not results:
                return {"success": True, "data": ""}

            import csv
            import io

            output = io.StringIO()
            if results:
                writer = csv.DictWriter(output, fieldnames=results[0].keys())
                writer.writeheader()
                writer.writerows(results)

            return {
                "success": True,
                "data": output.getvalue(),
            }
        else:
            raise HTTPException(status_code=400, detail="Unsupported export format")
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# ==================== 图谱生成路由 ====================

@router.post("/graph/generate")
async def generate_graph(data: Dict[str, Any],
    user=Depends(get_current_user)):
    """创建图谱生成任务（兼容前端）"""
    try:
        from odap.tasks import generate_graph_task

        scenario_id = data.get("scenario_id")
        config = data.get("config", {})

        if not scenario_id:
            raise HTTPException(status_code=400, detail="scenario_id is required")

        task_id = f"graph_task_{uuid.uuid4().hex[:12]}"

        task = generate_graph_task.delay(
            task_id,
            scenario_id,
            config,
        )

        return {
            "task_id": task_id,
            "status": "created",
            "scenario_id": scenario_id,
        }
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/graph/progress/{task_id}")
async def get_graph_progress(task_id: str,
    user=Depends(get_current_user)):
    """获取图谱生成进度（兼容前端）"""
    try:
        try:
            from celery.result import AsyncResult
            task_result = AsyncResult(task_id)
            if task_result.ready():
                result = task_result.get()
                return {
                    "task_id": task_id,
                    "status": "completed",
                    "progress": 100,
                    "entities_generated": result.get("entities_generated", 0) if isinstance(result, dict) else 0,
                    "relations_generated": result.get("relations_generated", 0) if isinstance(result, dict) else 0,
                }
            return {
                "task_id": task_id,
                "status": "pending",
                "progress": 50,
                "entities_generated": 0,
                "relations_generated": 0,
            }
        except ImportError:
            return {
                "task_id": task_id,
                "status": "completed",
                "progress": 100,
                "entities_generated": 0,
                "relations_generated": 0,
            }
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/graph/cancel/{task_id}")
async def cancel_graph_task(task_id: str,
    user=Depends(get_current_user)):
    """取消图谱生成任务（兼容前端）"""
    try:
        try:
            from celery.result import AsyncResult
            task_result = AsyncResult(task_id)
            task_result.revoke(terminate=True)
        except ImportError:
            pass
        return {
            "task_id": task_id,
            "status": "cancelled",
        }
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/graph/history")
async def get_graph_history(limit: int = Query(20, ge=1, le=100),
    user=Depends(get_current_user)):
    """获取图谱生成历史（兼容前端）"""
    try:
        from odap.biz.core.ontology.design.services.ingest_service import get_ingest_service
        ingest_service = get_ingest_service()
        versions = ingest_service.list_all_versions()
        history = []
        for v in versions[:limit]:
            history.append({
                "task_id": v.get("id", ""),
                "scenario_id": v.get("ontology_id", ""),
                "status": v.get("status", "completed"),
                "created_at": v.get("created_at", ""),
            })
        return {
            "history": history,
            "limit": limit,
            "total": len(history),
        }
    except HTTPException:
        raise
    except Exception as e:
        return {
            "history": [],
            "limit": limit,
            "total": 0,
        }


@router.get("/graph/{graph_id}")
async def get_graph_detail(graph_id: str,
    user=Depends(get_current_user)):
    """获取图谱详情（兼容前端）"""
    try:
        from odap.biz.core.ontology.design.services.ingest_service import get_ingest_service
        ingest_service = get_ingest_service()
        docs = ingest_service.get_version_documents(graph_id)
        nodes = []
        edges = []
        for doc in docs:
            entities = doc.get("entities", [])
            if isinstance(entities, str):
                try:
                    import json as _json
                    entities = _json.loads(entities)
                except HTTPException:
                    raise
                except Exception:
                    entities = []
            for e in entities:
                if isinstance(e, dict):
                    nodes.append({"id": e.get("entity_id", ""), "name": e.get("name", ""), "type": e.get("entity_type", "")})
            relations = doc.get("relations", [])
            if isinstance(relations, str):
                try:
                    import json as _json
                    relations = _json.loads(relations)
                except HTTPException:
                    raise
                except Exception:
                    relations = []
            for r in relations:
                if isinstance(r, dict):
                    edges.append({"id": r.get("relation_id", ""), "source": r.get("source_entity", ""), "target": r.get("target_entity", ""), "type": r.get("relation_type", "")})
        return {
            "graph_id": graph_id,
            "nodes": nodes,
            "edges": edges,
        }
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# ==================== 本体 Schema 路由 ====================

@router.get("/ontology/schema")
async def get_ontology_schema(user=Depends(get_current_user)):
    """获取当前本体定义Schema"""
    try:
        from odap.biz.core.ontology.design.schema.domain import ENTITY_TYPES, ROLES, DOMAIN_CONFIG, ONTOLOGY_VERSION, ONTOLOGY_LAST_UPDATED
        from odap.biz.core.ontology.design.schema.document import (
            OntologyDocument, OntologyEntity, OntologyRelation, OntologyEvent,
            OntologyAction, OntologyRule, OntologyConstraint, SourceInfo,
            DocumentMeta, TemporalInfo, VersionRef, DocType, SourceType,
            EntityType, ActionStatus,
        )
        from odap.biz.management.business.services import get_business_service
        biz_svc = get_business_service()

        def dataclass_to_schema(cls, enum_classes=None):
            import dataclasses
            schema = {"fields": {}, "doc": (cls.__doc__ or "").strip()}
            if dataclasses.is_dataclass(cls):
                for f in dataclasses.fields(cls):
                    type_name = getattr(f.type, '__name__', str(f.type))
                    if hasattr(f.type, '__args__'):
                        type_name = str(f.type)
                    schema["fields"][f.name] = {
                        "type": type_name,
                        "default": repr(f.default) if f.default is not dataclasses.MISSING else None,
                        "default_factory": f.default_factory.__name__ if f.default_factory is not dataclasses.MISSING and callable(f.default_factory) else None,
                    }
            if enum_classes:
                for name, enum_cls in enum_classes.items():
                    schema[name] = [e.value for e in enum_cls]
            return schema

        ontology_doc_schema = {
            "OntologyDocument": dataclass_to_schema(OntologyDocument),
            "OntologyEntity": dataclass_to_schema(OntologyEntity, {"EntityType": EntityType}),
            "OntologyRelation": dataclass_to_schema(OntologyRelation),
            "OntologyEvent": dataclass_to_schema(OntologyEvent),
            "OntologyAction": dataclass_to_schema(OntologyAction, {"ActionStatus": ActionStatus}),
            "OntologyRule": dataclass_to_schema(OntologyRule),
            "OntologyConstraint": dataclass_to_schema(OntologyConstraint),
            "DataSource": dataclass_to_schema(SourceInfo, {"SourceType": SourceType}),
            "DocumentMeta": dataclass_to_schema(DocumentMeta),
            "TemporalInfo": dataclass_to_schema(TemporalInfo),
            "VersionRef": dataclass_to_schema(VersionRef),
            "DocType": [e.value for e in DocType],
        }

        schema = {
            "version": ONTOLOGY_VERSION,
            "last_updated": ONTOLOGY_LAST_UPDATED,
            "entity_types": ENTITY_TYPES,
            "roles": ROLES,
            "domain_config": DOMAIN_CONFIG,
            "ontology_document_schema": ontology_doc_schema,
            "business_processes": biz_svc.list_processes(),
            "business_rules": biz_svc.list_rules(),
            "business_logics": biz_svc.list_logics(),
            "business_indicators": biz_svc.list_indicators(),
        }
        return schema
    except HTTPException:
        raise
    except Exception as e:
        from odap.biz.core.ontology.design.schema.domain import ENTITY_TYPES, ROLES, DOMAIN_CONFIG, ONTOLOGY_VERSION, ONTOLOGY_LAST_UPDATED
        return {
            "version": ONTOLOGY_VERSION,
            "last_updated": ONTOLOGY_LAST_UPDATED,
            "entity_types": ENTITY_TYPES,
            "roles": ROLES,
            "domain_config": DOMAIN_CONFIG,
            "ontology_document_schema": {},
            "business_processes": [],
            "business_rules": [],
            "business_logics": [],
            "business_indicators": [],
        }
