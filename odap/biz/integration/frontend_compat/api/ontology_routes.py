"""前端API兼容层 - 本体/图谱/场景路由

仅保留跨服务聚合端点。1:1 重复原生 /api/query/ 的端点已删除，
前端应直接调用:
  POST /api/query/entities    — 实体查询
  POST /api/query/relations   — 关系查询
  POST /api/query/complex     — 复合查询
  GET  /api/query/history     — 查询历史
"""

import logging

from fastapi import APIRouter, HTTPException, Query, Depends
from odap.infra.security.jwt_auth import get_current_user
from typing import Dict, Any
import json
import uuid

logger = logging.getLogger(__name__)

from odap.biz.integration.frontend_compat.api._deps import (
    scenario_store,
)

router = APIRouter(prefix="/api/compat", tags=["frontend-compat-ontology"])


# ==================== 场景查询路由（跨服务聚合） ====================

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


# ==================== 查询导出（原生 /api/query/ 无此能力） ====================

@router.post("/query/export")
async def export_query_results(data: Dict[str, Any],
    user=Depends(get_current_user)):
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


# ==================== 图谱生成任务（Celery 异步编排） ====================

@router.post("/graph/generate")
async def generate_graph(data: Dict[str, Any],
    user=Depends(get_current_user)):
    try:
        from odap.tasks import generate_graph_task

        scenario_id = data.get("scenario_id")
        config = data.get("config", {})

        if not scenario_id:
            raise HTTPException(status_code=400, detail="scenario_id is required")

        task_id = f"graph_task_{uuid.uuid4().hex[:12]}"

        generate_graph_task.delay(
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
    except Exception:
        return {
            "history": [],
            "limit": limit,
            "total": 0,
        }


@router.get("/graph/{graph_id}")
async def get_graph_detail(graph_id: str,
    user=Depends(get_current_user)):
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
                except Exception as e:
                    logger.debug("Query fallback: %s", e)
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
                except Exception as e:
                    logger.debug("Query fallback: %s", e)
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


# ==================== 本体 Schema（跨服务聚合：dataclass + 业务规则 + 领域配置） ====================

@router.get("/ontology/schema")
async def get_ontology_schema(user=Depends(get_current_user)):
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
    except Exception:
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
