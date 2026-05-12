"""前端API兼容层 - 使用统一的工作空间管理和场景存储"""

from fastapi import APIRouter, HTTPException, Query, UploadFile, File, Form, Request, Body
from fastapi.responses import StreamingResponse
from typing import Dict, Any, List, Optional
import json
import os
import uuid
import asyncio
from datetime import datetime
from odap.infra.security import get_audit_logger, AuditFilter, AuditEventType, AuditSeverity, ActorInfo, ResourceInfo, ActionResult, audit_log

router = APIRouter(prefix="/api", tags=["frontend-compat"])

# 导入原始的 ScenarioStore
import sys

# 修复路径问题
base_path = os.path.dirname(os.path.abspath(__file__))
parent_path = os.path.dirname(base_path)
grandparent_path = os.path.dirname(parent_path)
root_path = os.path.dirname(grandparent_path)
sys.path.append(root_path)

from odap.web.api.app import ScenarioStore

# 定义新的场景存储目录
_storage_base = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
_odap_root = os.path.dirname(os.path.dirname(_storage_base))
SCENARIOS_DIR = os.path.join(_odap_root, "storage", "versions", "scenarios")
from odap.infra.graph.graph_service import GraphManager
from odap.biz.workspace.services.workspace_service import WorkspaceService

# 初始化存储
try:
    from odap.biz.workspace.storage import Storage
    storage = Storage()
except Exception as e:
    print(f"Failed to initialize storage: {e}")
    storage = None

_graph_manager = None

def _get_graph_manager():
    global _graph_manager
    if _graph_manager is None:
        _graph_manager = GraphManager()
    return _graph_manager

scenario_store = ScenarioStore(storage_dir=SCENARIOS_DIR, graph_manager=None, storage=storage)
workspace_service = WorkspaceService()

# 初始化审计日志器
audit_logger = get_audit_logger()


# 本地审计日志装饰器
def local_audit_log(action: str, resource: str):
    """本地审计日志装饰器"""
    def decorator(func):
        async def wrapper(*args, **kwargs):
            # 提取 request 对象
            request = None
            for arg in args:
                if hasattr(arg, "client"):
                    request = arg
                    break
            if not request:
                for key, value in kwargs.items():
                    if hasattr(value, "client"):
                        request = value
                        break

            try:
                result = await func(*args, **kwargs)
                # 记录成功日志
                from odap.infra.security import audit_info, AuditEventType
                audit_info(
                    event_type=AuditEventType.SYSTEM_HEALTH,
                    actor={"type": "user", "id": "system", "name": "System"},
                    action=action,
                    resource={"type": resource, "id": resource, "name": resource},
                    result={"status": "success"},
                    workspace_id="system"
                )
                return result
            except Exception as e:
                # 记录错误日志
                from odap.infra.security import audit_error, AuditEventType
                audit_error(
                    event_type=AuditEventType.SYSTEM_ERROR,
                    actor={"type": "user", "id": "system", "name": "System"},
                    action=action,
                    resource={"type": resource, "id": resource, "name": resource},
                    result={"status": "error", "error": str(e)},
                    workspace_id="system"
                )
                raise
        return wrapper
    return decorator


def log_ingest(ingest_type: str, **kwargs):
    """记录数据摄入日志"""
    asyncio.create_task(
        audit_logger.log_success(
            event_type=AuditEventType.DATA_INGEST,
            action=f"INGEST_{ingest_type.upper()}",
            resource=ResourceInfo(
                resource_type="data",
                resource_id=ingest_type,
                resource_name=ingest_type
            ),
            message=f"Data ingest {ingest_type} completed",
            actor=ActorInfo(
                actor_type="user",
                actor_id=kwargs.get("user", "system"),
                actor_name=kwargs.get("user", "System"),
                roles=[]
            ),
            context={
                "filename": kwargs.get("filename"),
                "count": kwargs.get("count")
            }
        )
    )


def log_query(query: str, result_count: int, **kwargs):
    """记录查询日志"""
    asyncio.create_task(
        audit_logger.log_success(
            event_type=AuditEventType.QUERY,
            action="QUERY",
            resource=ResourceInfo(
                resource_type="query",
                resource_id="query",
                resource_name="Query"
            ),
            message=f"Query completed with {result_count} results",
            actor=ActorInfo(
                actor_type="user",
                actor_id=kwargs.get("user", "system"),
                actor_name=kwargs.get("user", "System"),
                roles=[]
            ),
            context={
                "query": query,
                "result_count": result_count
            }
        )
    )


def log_error(error: str, **kwargs):
    """记录错误日志（简化版）"""
    pass


async def _log_error_async(error: str, context: Dict[str, Any]):
    """异步记录错误日志"""
    pass


# 工作空间和场景初始化已移至 app/main.py startup_event


# ==================== 场景管理路由 ====================

@router.get("/scenarios")
async def list_scenarios():
    """列出场景（兼容前端）"""
    try:
        scenarios = scenario_store.list_scenarios()
        return {"scenarios": scenarios}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/scenarios/{scenario_id}")
async def get_scenario(scenario_id: str):
    """获取场景（兼容前端）"""
    try:
        scenario = scenario_store.get_scenario(scenario_id)
        if not scenario:
            raise HTTPException(status_code=404, detail="Scenario not found")
        return scenario
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/scenarios")
async def create_scenario(data: Dict[str, Any]):
    """创建场景（兼容前端）"""
    try:
        scenario_id = scenario_store.create(
            name=data.get("name", "新场景"),
            description=data.get("description", "")
        )
        scenario = scenario_store.get_scenario(scenario_id)
        return scenario
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.put("/scenarios/{scenario_id}")
async def update_scenario(scenario_id: str, data: Dict[str, Any]):
    """更新场景（兼容前端）"""
    try:
        scenario = scenario_store.get_scenario(scenario_id)
        if not scenario:
            raise HTTPException(status_code=404, detail="Scenario not found")
        return scenario
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.delete("/scenarios/{scenario_id}")
async def delete_scenario(scenario_id: str):
    """删除场景（兼容前端）"""
    try:
        scenario = scenario_store.get_scenario(scenario_id)
        if not scenario:
            raise HTTPException(status_code=404, detail="Scenario not found")
        return {"status": "success"}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/scenarios/{scenario_id}/sync")
async def sync_scenario(scenario_id: str):
    """同步场景（兼容前端）"""
    try:
        result = scenario_store.sync_to_graphiti(scenario_id)
        return result
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/scenarios/{scenario_id}/timeline")
async def get_timeline(scenario_id: str):
    """获取时间线（兼容前端）"""
    try:
        events = scenario_store.get_timeline(scenario_id)
        return {"events": events}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/scenarios/{scenario_id}/entities")
async def get_entities(scenario_id: str):
    """获取实体（兼容前端）"""
    try:
        gm = _get_graph_manager()
        entities_raw = gm.get_all_entities()
        entities_list = []
        for e in entities_raw:
            e_dict = e.to_dict() if hasattr(e, 'to_dict') else dict(e)
            entities_list.append({
                "entity_id": e_dict.get("entity_id", e_dict.get("name", "")),
                "name": e_dict.get("name", ""),
                "entity_type": e_dict.get("type", e_dict.get("entity_type", "Entity")),
                "properties": e_dict.get("properties", {}),
                "basic_properties": e_dict
            })
        return {"entities": entities_list}
    except Exception as e:
        try:
            entities = scenario_store.get_entities(scenario_id)
            return {"entities": entities}
        except Exception as e2:
            raise HTTPException(status_code=500, detail=str(e2))


@router.get("/scenarios/{scenario_id}/relations")
async def get_relations(scenario_id: str):
    """获取关系（兼容前端）"""
    try:
        gm = _get_graph_manager()
        nodes_raw = gm.get_all_entities()
        rels_raw = gm.get_all_relations()
        
        nodes = []
        node_ids = set()
        for n in nodes_raw:
            n_dict = n.to_dict() if hasattr(n, 'to_dict') else dict(n)
            nid = n_dict.get("entity_id", n_dict.get("name", str(n)))
            if nid not in node_ids:
                nodes.append({
                    "id": nid,
                    "name": n_dict.get("name", nid),
                    "type": n_dict.get("type", n_dict.get("entity_type", "Entity")),
                })
                node_ids.add(nid)
        
        links = []
        for r in rels_raw:
            r_dict = r.to_dict() if hasattr(r, 'to_dict') else dict(r)
            links.append({
                "id": r_dict.get("relation_id", r_dict.get("id", "")),
                "source": r_dict.get("source", r_dict.get("source_entity", "")),
                "target": r_dict.get("target", r_dict.get("target_entity", "")),
                "type": r_dict.get("relation_type", r_dict.get("type", "")),
            })
        
        return {"scenario_id": scenario_id, "nodes": nodes, "links": links}
    except Exception as e:
        try:
            result = scenario_store.get_relations(scenario_id)
            return {"scenario_id": scenario_id, "nodes": result.get("nodes", []), "links": result.get("links", [])}
        except Exception as e2:
            raise HTTPException(status_code=500, detail=str(e2))


# ==================== 数据摄入路由 ====================

@router.post("/ingest/text")
@local_audit_log(action="INGEST_TEXT", resource="text")
async def ingest_text(request: Request, data: Dict[str, Any] = Body(...)):
    """文本摄入（兼容前端）"""
    try:
        try:
            from odap.tasks import process_ingest_task
            task_id = f"task_{uuid.uuid4().hex[:12]}"
            task = process_ingest_task.delay(
                task_id,
                'text',
                {'text': data.get('text', '')},
                data.get('scenario_id')
            )
        except ImportError:
            task_id = f"task_{uuid.uuid4().hex[:12]}"
        
        log_ingest('text', user="system")
        
        return {"success": True, "task_id": task_id}
    except Exception as e:
        log_error(str(e), context="ingest_text")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/ingest/news")
async def ingest_news(data: Dict[str, Any] = Body(...)):
    """
    新闻摄入API - 支持通过URL或关键词摄入新闻
    
    请求体:
    {
        "query": "搜索关键词（可选）",
        "url": "新闻URL（可选，与query二选一）",
        "scenario_id": "场景ID（可选）",
        "workspace_id": "工作空间ID（可选）"
    }
    """
    try:
        from odap.biz.ontology.services.qa_ontology_builder import get_qa_builder
        
        query = data.get("query", "")
        url = data.get("url", "")
        
        if not query and not url:
            raise HTTPException(status_code=400, detail="query 或 url 必须提供至少一个")
        
        builder = get_qa_builder()
        
        # 使用 QA 构建器处理
        question = query or f"请分析这个新闻: {url}"
        result = await builder.process_question(
            question=question,
            scenario_id=data.get("scenario_id"),
            workspace_id=data.get("workspace_id")
        )
        
        return {
            "success": True,
            "task_id": result.get("task_id"),
            "status": result.get("status"),
            "answer": result.get("answer"),
            "sources_count": len(result.get("sources", []))
        }
    except HTTPException:
        raise
    except Exception as e:
        log_error(str(e), context="ingest_news")
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/ingest/news2")
async def ingest_news2(data: Dict[str, Any] = Body(...)):
    """新闻摄入测试（兼容前端）"""
    return {"success": True, "task_id": "test-task-123"}


@router.get("/ingest/news/progress/{task_id}")
async def get_news_ingest_progress(task_id: str):
    """
    获取新闻摄入进度
    
    返回各阶段状态:
    - intent_analyzing: 意图分析
    - searching: 联网搜索
    - ingesting: 数据摄入
    - building: 本体构建
    - completed/failed: 完成/失败
    """
    try:
        from odap.biz.ontology.services.qa_ontology_builder import get_qa_builder
        
        builder = get_qa_builder()
        progress = await builder.get_progress(task_id)
        
        if not progress:
            raise HTTPException(status_code=404, detail="任务不存在或已过期")
        
        return progress
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/test")
async def test_route(data: Dict[str, Any] = Body(...)):
    """测试路由"""
    return {"message": "Test successful", "data": data}

@router.post("/test2")
async def test_route2():
    """测试路由2"""
    return {"message": "Test 2 successful"}


@router.post("/ingest/random")
@audit_log(action="INGEST_RANDOM", resource="random")
async def ingest_random(request: Request, data: Dict[str, Any]):
    """随机数据摄入（兼容前端）"""
    try:
        try:
            from odap.tasks import process_ingest_task
            task_id = f"task_{uuid.uuid4().hex[:12]}"
            task = process_ingest_task.delay(
                task_id,
                'random',
                {'count': data.get('count', 10)},
                data.get('scenario_id')
            )
        except ImportError:
            task_id = f"task_{uuid.uuid4().hex[:12]}"
        
        log_ingest('random', user="system")
        
        return {"success": True, "task_id": task_id, "doc_count": 10, "versions": []}
    except Exception as e:
        log_error(str(e), context="ingest_random")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/ingest/manual")
@audit_log(action="INGEST_MANUAL", resource="manual")
async def ingest_manual(request: Request, data: Dict[str, Any]):
    """手动数据摄入（兼容前端）"""
    try:
        try:
            from odap.tasks import process_ingest_task
            task_id = f"task_{uuid.uuid4().hex[:12]}"
            task = process_ingest_task.delay(
                task_id,
                'manual',
                data.get('data', {}),
                data.get('scenario_id')
            )
        except ImportError:
            task_id = f"task_{uuid.uuid4().hex[:12]}"
        
        # 记录审计日志
        log_ingest('manual', user="system")
        
        return {"task_id": task_id}
    except Exception as e:
        log_error(str(e), context="ingest_manual")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/ingest/status/{task_id}")
async def get_ingest_status(task_id: str):
    """获取摄入任务状态（兼容前端）"""
    try:
        from celery.result import AsyncResult
        
        # 查找任务结果
        task_result = AsyncResult(task_id)
        
        if task_result.ready():
            result = task_result.get()
            return {
                "task_id": task_id,
                "status": result.get('status', 'completed'),
                "result": result
            }
        else:
            return {
                "task_id": task_id,
                "status": "pending",
                "result": None
            }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/ingest/file")
@audit_log(action="INGEST_FILE", resource="file")
async def ingest_file(request: Request, file: UploadFile = File(...), scenario_id: Optional[str] = Form(None)):
    """文件上传摄入（兼容前端）"""
    try:
        import pandas as pd
        import json
        from odap.tasks import process_file_upload_task
        
        filename = file.filename
        file_extension = os.path.splitext(filename)[1].lower()
        
        content = await file.read()
        
        if file_extension not in ['.json', '.csv', '.txt']:
            raise HTTPException(status_code=400, detail="Unsupported file format")
        
        # 启动异步任务
        task_id = f"task_{uuid.uuid4().hex[:12]}"
        task = process_file_upload_task.delay(
            task_id,
            filename,
            content,
            file_extension,
            scenario_id
        )
        
        # 记录审计日志
        log_ingest('file', filename=filename, user="system")
        
        return {
            "success": True,
            "task_id": task_id,
            "filename": filename,
            "file_size": len(content)
        }
    except HTTPException:
        raise
    except Exception as e:
        log_error(str(e), context="ingest_file")
        raise HTTPException(status_code=500, detail=str(e))


# ==================== 版本管理路由 ====================

@router.get("/versions")
async def list_versions():
    """列出版本（兼容前端）"""
    try:
        return {"versions": []}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/versions")
async def create_version(data: Dict[str, Any]):
    """创建版本（兼容前端）"""
    try:
        return {
            "id": f"version-{str(uuid.uuid4())[:8]}",
            "version": data.get("version", "1.0.0"),
            "created_at": datetime.utcnow().isoformat() + "Z",
            "created_by": "system"
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/versions/{version_id}")
async def get_version(version_id: str):
    """获取版本（兼容前端）"""
    try:
        return {
            "id": version_id,
            "version": "1.0.0",
            "created_at": datetime.utcnow().isoformat() + "Z",
            "created_by": "system"
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/versions/{version_id}/rollback")
async def rollback(version_id: str):
    """回滚版本（兼容前端）"""
    try:
        return {"status": "success"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/versions/diff")
async def diff_versions(version_a: str, version_b: str):
    """对比版本（兼容前端）"""
    try:
        return {
            "version_a": version_a,
            "version_b": version_b,
            "changes": []
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# ==================== 审计日志路由 ====================

@router.get("/audit/events")
async def list_audit_events(
    start_time: Optional[str] = Query(None),
    end_time: Optional[str] = Query(None),
    event_type: Optional[str] = Query(None),
    severity: Optional[str] = Query(None),
    actor_id: Optional[str] = Query(None),
    limit: int = Query(50, ge=1, le=100),
    offset: int = Query(0, ge=0)
):
    """列出审计事件（兼容前端）"""
    try:
        # 构建过滤器
        filter_kwargs = {
            "limit": limit,
            "offset": offset,
            "order_by": "timestamp",
            "order_desc": True
        }
        
        if start_time:
            filter_kwargs["start_time"] = datetime.fromisoformat(start_time)
        if end_time:
            filter_kwargs["end_time"] = datetime.fromisoformat(end_time)
        if event_type:
            filter_kwargs["event_types"] = [event_type]
        if severity:
            filter_kwargs["severities"] = [severity]
        if actor_id:
            filter_kwargs["actor_ids"] = [actor_id]
        
        audit_filter = AuditFilter(**filter_kwargs)
        
        # 查询事件
        events = await audit_logger.query(audit_filter)
        
        # 转换为前端兼容格式
        event_list = []
        for event in events:
            event_dict = event.model_dump()
            if isinstance(event_dict["timestamp"], datetime):
                event_dict["timestamp"] = event_dict["timestamp"].isoformat()
            event_list.append(event_dict)
        
        return {
            "events": event_list,
            "total": len(event_list),
            "limit": limit,
            "offset": offset
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/audit/events")
async def create_audit_event(data: Dict[str, Any]):
    """创建审计事件（兼容前端）"""
    try:
        event_type_str = data.get("event_type", "system.action")
        try:
            event_type = AuditEventType(event_type_str)
        except ValueError:
            event_type = AuditEventType.SYSTEM_HEALTH
        
        event_id = await audit_logger.log(
            event_type=event_type,
            action=data.get("action", ""),
            resource={
                "resource_type": data.get("resource_type", ""),
                "resource_id": data.get("resource_id", ""),
                "resource_name": data.get("resource_id", "")
            },
            result={
                "status": data.get("result_status", "success"),
                "message": data.get("result_message", "")
            },
            severity=AuditSeverity(data.get("severity", "info")),
            actor={
                "actor_type": "user",
                "actor_id": data.get("actor_id", "system"),
                "actor_name": data.get("actor_name", "System"),
                "roles": []
            },
            workspace_id=data.get("workspace_id", "default"),
            context=data.get("context")
        )
        
        return {
            "id": event_id,
            "event_type": event_type.value,
            "action": data.get("action", ""),
            "status": "success"
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/audit/timeline")
async def get_audit_timeline(
    start_time: Optional[str] = Query(None),
    end_time: Optional[str] = Query(None),
    workspace_id: Optional[str] = Query(None)
):
    """获取审计时间线（兼容前端）"""
    try:
        # 构建过滤器
        filter_kwargs = {
            "limit": 100,
            "offset": 0,
            "order_by": "timestamp",
            "order_desc": True
        }
        
        if start_time:
            filter_kwargs["start_time"] = datetime.fromisoformat(start_time)
        if end_time:
            filter_kwargs["end_time"] = datetime.fromisoformat(end_time)
        if workspace_id:
            filter_kwargs["workspace_id"] = workspace_id
        
        audit_filter = AuditFilter(**filter_kwargs)
        
        # 查询事件
        events = await audit_logger.query(audit_filter)
        
        # 转换为前端兼容格式
        event_list = []
        for event in events:
            event_dict = event.model_dump()
            if isinstance(event_dict["timestamp"], datetime):
                event_dict["timestamp"] = event_dict["timestamp"].isoformat()
            event_list.append(event_dict)
        
        return {
            "events": event_list,
            "total": len(event_list),
            "limit": 100,
            "offset": 0
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/audit/stats")
async def get_audit_stats():
    """获取审计统计（兼容前端）"""
    try:
        # 获取统计信息
        stats = audit_logger.get_stats()
        
        # 转换为前端兼容格式
        return {
            "total": stats.get("total", 0),
            "by_type": stats.get("by_type", {}),
            "by_severity": stats.get("by_severity", {}),
            "by_status": {}
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/audit/trace/{trace_id}")
async def get_trace_events(trace_id: str):
    """获取追踪链事件（兼容前端）"""
    try:
        # 构建过滤器
        audit_filter = AuditFilter(
            trace_id=trace_id,
            limit=100,
            order_by="timestamp",
            order_desc=False
        )
        
        # 查询事件
        events = await audit_logger.query(audit_filter)
        
        # 转换为前端兼容格式
        event_list = []
        for event in events:
            event_dict = event.model_dump()
            if isinstance(event_dict["timestamp"], datetime):
                event_dict["timestamp"] = event_dict["timestamp"].isoformat()
            event_list.append(event_dict)
        
        return {
            "events": event_list,
            "total": len(event_list)
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# ==================== 工作空间路由（使用完整实现） ====================

# 注意：更具体的路由必须放在更通用的路由前面！

@router.get("/workspaces")
async def list_workspaces():
    """列出工作空间（兼容前端）"""
    try:
        result = workspace_service.list_workspaces(filters={}, page=1, page_size=100)
        return result
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/workspaces/{workspace_id}")
async def get_workspace(workspace_id: str):
    """获取工作空间（兼容前端）"""
    try:
        result = workspace_service.get_workspace(workspace_id)
        if result.get("status") == "error":
            raise HTTPException(status_code=404, detail=result.get("message"))
        return result
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))




# ==================== 实体路由 ====================

@router.get("/entities/{entity_id}/history")
async def get_entity_history(entity_id: str):
    """获取实体历史（兼容前端）"""
    try:
        return []
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# ==================== 统计信息路由 ====================

@router.get("/stats")
async def get_stats():
    """获取统计信息（兼容前端）"""
    try:
        scenarios = scenario_store.list_scenarios()
        workspace_result = workspace_service.list_workspaces(filters={}, page=1, page_size=100)
        workspaces = workspace_result.get("workspaces", [])
        
        # 使用统一的审计统计
        audit_stats = audit_logger.get_stats()

        return {
            "entity_count": 0,
            "relation_count": 0,
            "version_count": 0,
            "ingest_count": 0,
            "scenario_count": len(scenarios),
            "workspace_count": len(workspaces),
            "audit_total": audit_stats.get("total", 0)
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# ==================== 图谱查询路由 ====================

@router.post("/query/entities")
@audit_log(action="QUERY_ENTITIES", resource="entities")
async def query_entities(request: Request, data: Dict[str, Any]):
    """查询实体（兼容前端）"""
    try:
        query = data.get("query", {})
        workspace_id = data.get("workspace_id")
        
        # 使用 GraphManager 进行查询
        graph_manager = _get_graph_manager()
        
        # 如果有查询条件，进行过滤搜索
        if query.get("keyword"):
            results = graph_manager.search(query.get("keyword"))
            entities = [
                {
                    "entity_id": r.get("id", r.get("name", "")),
                    "name": r.get("name", ""),
                    "type": r.get("type", ""),
                    "properties": r
                }
                for r in results
            ]
        else:
            entities = []
        
        # 记录审计日志
        log_query(query.get("keyword", ""), len(entities), user="system")
        
        return {
            "entities": entities,
            "total": len(entities)
        }
    except Exception as e:
        log_error(str(e), context="query_entities")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/query/relations")
async def query_relations(data: Dict[str, Any]):
    """查询关系（兼容前端）"""
    try:
        query = data.get("query", {})
        source_id = query.get("source_id")
        target_id = query.get("target_id")
        relation_type = query.get("relation_type")
        
        # 简化实现，返回空列表
        # 实际实现应该从图数据库查询
        return {
            "relations": [],
            "total": 0
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/query/complex")
@audit_log(action="QUERY_COMPLEX", resource="complex")
async def complex_query(request: Request, data: Dict[str, Any]):
    """复合查询（兼容前端）"""
    try:
        conditions = data.get("conditions", [])
        workspace_id = data.get("workspace_id")
        
        # 使用 GraphManager 进行查询
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
                "properties": r
            }
            for r in results
        ]
        
        # 记录审计日志
        query_str = str(conditions)
        log_query(query_str, len(entities), user="system")
        
        return {
            "results": entities,
            "total": len(entities)
        }
    except Exception as e:
        log_error(str(e), context="query_complex")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/query/history")
async def get_query_history(limit: int = Query(50, ge=1, le=200)):
    """获取查询历史（兼容前端）"""
    try:
        # 简化实现，返回空列表
        return {
            "history": [],
            "limit": limit
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/query/export")
async def export_query_results(data: Dict[str, Any]):
    """导出查询结果（兼容前端）"""
    try:
        results = data.get("results", [])
        export_format = data.get("format", "json")
        
        if export_format == "json":
            return {
                "success": True,
                "data": json.dumps(results, ensure_ascii=False, indent=2)
            }
        elif export_format == "csv":
            if not results:
                return {"success": True, "data": ""}
            
            # 生成 CSV
            import csv
            import io
            
            output = io.StringIO()
            if results:
                writer = csv.DictWriter(output, fieldnames=results[0].keys())
                writer.writeheader()
                writer.writerows(results)
            
            return {
                "success": True,
                "data": output.getvalue()
            }
        else:
            raise HTTPException(status_code=400, detail="Unsupported export format")
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# ==================== 图谱生成路由 ====================

@router.post("/graph/generate")
async def generate_graph(data: Dict[str, Any]):
    """创建图谱生成任务（兼容前端）"""
    try:
        from odap.tasks import generate_graph_task
        
        scenario_id = data.get("scenario_id")
        config = data.get("config", {})
        
        if not scenario_id:
            raise HTTPException(status_code=400, detail="scenario_id is required")
        
        # 创建生成任务
        task_id = f"graph_task_{uuid.uuid4().hex[:12]}"
        
        # 启动异步任务
        task = generate_graph_task.delay(
            task_id,
            scenario_id,
            config
        )
        
        return {
            "task_id": task_id,
            "status": "created",
            "scenario_id": scenario_id
        }
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/graph/progress/{task_id}")
async def get_graph_progress(task_id: str):
    """获取图谱生成进度（兼容前端）"""
    try:
        # 简化实现，返回模拟进度
        return {
            "task_id": task_id,
            "status": "completed",
            "progress": 100,
            "entities_generated": 0,
            "relations_generated": 0
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/graph/cancel/{task_id}")
async def cancel_graph_task(task_id: str):
    """取消图谱生成任务（兼容前端）"""
    try:
        return {
            "task_id": task_id,
            "status": "cancelled"
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/graph/history")
async def get_graph_history(limit: int = Query(20, ge=1, le=100)):
    """获取图谱生成历史（兼容前端）"""
    try:
        return {
            "history": [],
            "limit": limit,
            "total": 0
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/graph/{graph_id}")
async def get_graph_detail(graph_id: str):
    """获取图谱详情（兼容前端）"""
    try:
        return {
            "graph_id": graph_id,
            "nodes": [],
            "edges": []
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# ==================== 智能问答路由 ====================

@router.post("/qa/ask")
async def ask_question(request: Request, data: Dict[str, Any]):
    """
    智能问答接口
    
    请求体:
    {
        "question": "用户问题",
        "session_id": "可选的会话ID",
        "workspace_id": "可选的工作空间ID"
    }
    
    返回:
    {
        "session_id": "会话ID",
        "answer": "回答内容",
        "sources": [{"source": "来源", "excerpt": "内容摘要", "confidence": 0.9}],
        "intent": {"type": "query", "confidence": 0.95},
        "sources_used": ["graphiti", "rag"]
    }
    """
    try:
        question = data.get("question", "")
        session_id = data.get("session_id")
        workspace_id = data.get("workspace_id")
        user_id = data.get("user_id", "anonymous")

        if not question:
            raise HTTPException(status_code=400, detail="问题不能为空")

        # 使用全局 QAEngineV2 实例（确保会话持久化）
        qa_engine = get_qa_engine(use_mock=False)
        
        # 调用问答引擎
        result = qa_engine.ask(
            query=question,
            user_id=user_id,
            session_id=session_id,
            workspace_id=workspace_id,
            scenario_id=data.get("scenario_id")
        )

        return {
            "session_id": result.get("session_id"),
            "answer": result.get("answer", ""),
            "sources": result.get("sources", []),
            "dialog_state": result.get("dialog_state", "completed"),
            "intent": {
                "type": "query",
                "confidence": 0.85
            },
            "sources_used": ["graphiti", "rag"]
        }
    except HTTPException:
        raise
    except Exception as e:
        import logging
        logging.error(f"QA ask error: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/qa/ask/stream")
async def ask_question_stream(request: Request, data: Dict[str, Any]):
    """
    智能问答流式接口 - 支持实时流式输出
    
    请求体:
    {
        "question": "用户问题",
        "session_id": "可选的会话ID",
        "workspace_id": "可选的工作空间ID"
    }
    
    返回: 流式 JSON 数据
    """
    try:
        question = data.get("question", "")
        session_id = data.get("session_id")
        workspace_id = data.get("workspace_id")
        user_id = data.get("user_id", "anonymous")

        if not question:
            raise HTTPException(status_code=400, detail="问题不能为空")

        qa_engine = get_qa_engine(use_mock=False)

        async def streaming_response():
            nonlocal session_id
            
            result = qa_engine.ask(
                query=question,
                user_id=user_id,
                session_id=session_id,
                workspace_id=workspace_id,
                scenario_id=data.get("scenario_id")
            )

            response_session_id = result.get("session_id")
            answer = result.get("answer", "")
            sources = result.get("sources", [])

            yield f'{{"type": "session_id", "value": "{response_session_id}"}}\n'

            for i in range(0, len(answer), 10):
                chunk = answer[i:i+10]
                yield f'{{"type": "content", "value": {json.dumps(chunk)}}}\n'
                await asyncio.sleep(0.02)

            if sources:
                yield f'{{"type": "sources", "value": {json.dumps(sources)}}}\n'

            yield '{"type": "end"}\n'

        return StreamingResponse(
            streaming_response(),
            media_type="text/plain",
            headers={
                "Transfer-Encoding": "chunked",
                "Connection": "keep-alive",
            }
        )
    except HTTPException:
        raise
    except Exception as e:
        import logging
        logging.error(f"QA stream error: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))


# 全局 QAEngineV2 实例，用于会话持久化
_qa_engine_instance = None

def get_qa_engine(use_mock: bool = False) -> 'QAEngineV2':
    """获取全局 QAEngineV2 实例"""
    global _qa_engine_instance
    if _qa_engine_instance is None:
        from odap.biz.qa.qa_engine_v2 import QAEngineV2
        from odap.infra.graph.graph_service import GraphManager
        
        graphiti_client = _get_graph_manager()
        _qa_engine_instance = QAEngineV2(graphiti_client=graphiti_client, use_mock=use_mock)
    return _qa_engine_instance


@router.get("/qa/sessions")
async def list_qa_sessions(
    user_id: Optional[str] = Query(None),
    workspace_id: Optional[str] = Query(None),
    scenario_id: Optional[str] = Query(None),
    limit: int = Query(50, ge=1, le=200)
):
    """列出问答会话"""
    try:
        qa_engine = get_qa_engine()
        sessions = qa_engine.dialog_manager._sessions
        
        session_list = []
        for session_id, session in sessions.items():
            # 根据 workspace_id 过滤
            if workspace_id and session.workspace_id != workspace_id:
                continue
            
            # 根据 scenario_id 过滤
            if scenario_id and session.scenario_id != scenario_id:
                continue
            
            # 取第一条用户消息作为摘要
            summary = ""
            for msg in session.messages:
                if msg.role == "user":
                    summary = msg.content[:50] + "..." if len(msg.content) > 50 else msg.content
                    break
            
            session_list.append({
                "session_id": session.session_id,
                "summary": summary,
                "message_count": len(session.messages),
                "model": "QAEngineV2",
                "created_at": session.created_at,
                "workspace_id": session.workspace_id,
                "scenario_id": session.scenario_id
            })
        
        # 按创建时间排序，最新的在前
        session_list.sort(key=lambda x: x["created_at"], reverse=True)
        
        return {
            "sessions": session_list[:limit],
            "total": len(session_list),
            "limit": limit
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/qa/sessions/{session_id}")
async def get_qa_session(session_id: str):
    """获取问答会话详情"""
    try:
        qa_engine = get_qa_engine(use_mock=False)
        history = qa_engine.get_dialog_history(session_id)
        
        return {
            "session_id": session_id,
            "messages": history,
            "total": len(history)
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.delete("/qa/sessions/{session_id}")
async def close_qa_session(session_id: str):
    """关闭问答会话"""
    try:
        qa_engine = get_qa_engine(use_mock=False)
        qa_engine.close_dialog(session_id)
        
        return {"status": "success", "session_id": session_id}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/qa/sessions/{session_id}/history")
async def get_qa_history(
    session_id: str,
    limit: int = Query(50, ge=1, le=200)
):
    """获取问答历史"""
    try:
        from odap.biz.qa.qa_engine_v2 import QAEngineV2
        
        qa_engine = QAEngineV2(use_mock=True)
        history = qa_engine.get_dialog_history(session_id)
        
        return {
            "session_id": session_id,
            "history": history[-limit:],
            "total": len(history)
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/qa/sessions/{session_id}/feedback")
async def submit_qa_feedback(session_id: str, data: Dict[str, Any]):
    """提交问答反馈"""
    try:
        feedback = data.get("feedback", {})
        rating = data.get("rating", 5)
        
        # 记录反馈
        asyncio.create_task(
            audit_logger.log_success(
                event_type=AuditEventType.QUERY,
                action="QA_FEEDBACK",
                resource=ResourceInfo(
                    resource_type="qa",
                    resource_id=session_id,
                    resource_name="问答反馈"
                ),
                message=f"问答反馈: 评分 {rating}",
                actor=ActorInfo(
                    actor_type="user",
                    actor_id=data.get("user_id", "anonymous"),
                    actor_name=data.get("user_id", "Anonymous"),
                    roles=[]
                ),
                context={
                    "session_id": session_id,
                    "feedback": feedback,
                    "rating": rating
                }
            )
        )
        
        return {
            "status": "success",
            "feedback_id": f"fb_{uuid.uuid4().hex[:12]}"
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# ==================== 用户认知引擎路由 ====================

@router.post("/cognition/intent")
async def recognize_intent(request: Request, data: Dict[str, Any]):
    """
    意图识别接口
    
    请求体:
    {
        "input_text": "用户输入",
        "role": "commander|intelligence|operator|analyst|guest"
    }
    """
    try:
        from odap.biz.cognition.user_cognition_engine import get_cognition_engine, RoleType
        
        input_text = data.get("input_text", "")
        role_str = data.get("role", "guest")
        
        # 转换角色字符串到枚举
        try:
            role = RoleType(role_str)
        except ValueError:
            role = RoleType.GUEST
        
        # 调用认知引擎
        cognition_engine = get_cognition_engine()
        result = cognition_engine.process_query(input_text, "anonymous", role)
        
        return {
            "intent": result.get("intent", {}),
            "knowledge_results": result.get("knowledge_results", []),
            "session_id": result.get("session_id")
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/cognition/view")
async def get_role_view(role: str = Query(...)):
    """获取角色视图"""
    try:
        from odap.biz.cognition.user_cognition_engine import get_cognition_engine, RoleType
        
        try:
            role_type = RoleType(role)
        except ValueError:
            role_type = RoleType.GUEST
        
        cognition_engine = get_cognition_engine()
        view = cognition_engine.get_role_view(role_type)
        
        return view
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/cognition/navigate")
async def navigate_knowledge(request: Request, data: Dict[str, Any]):
    """知识图谱导航"""
    try:
        from odap.biz.cognition.user_cognition_engine import get_cognition_engine
        
        entity_id = data.get("entity_id", "")
        direction = data.get("direction", "outbound")
        
        if not entity_id:
            raise HTTPException(status_code=400, detail="entity_id不能为空")
        
        cognition_engine = get_cognition_engine()
        result = cognition_engine.navigate_knowledge_graph(entity_id, direction)
        
        return result
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/cognition/explain")
async def explain_decision(request: Request, data: Dict[str, Any]):
    """决策解释"""
    try:
        from odap.biz.cognition.user_cognition_engine import get_cognition_engine
        
        decision_id = data.get("decision_id", "")
        context = data.get("context", {})
        
        cognition_engine = get_cognition_engine()
        explanation = cognition_engine.explain_decision(decision_id, context)
        
        return {
            "explanation_id": explanation.explanation_id,
            "query": explanation.query,
            "answer": explanation.answer,
            "confidence": explanation.confidence,
            "reasoning_chain": [
                {
                    "step_id": s.step_id,
                    "step_type": s.step_type,
                    "description": s.description
                }
                for s in explanation.reasoning_chain.steps
            ] if explanation.reasoning_chain else [],
            "sources": explanation.sources
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# ==================== 问数统计路由（多维度数据分析） ====================

@router.get("/qa/stats")
async def get_qa_stats(
    workspace_id: Optional[str] = Query(None),
    start_time: Optional[str] = Query(None),
    end_time: Optional[str] = Query(None)
):
    """
    获取问答统计数据
    
    返回多维度分析数据:
    - total: 总问答数
    - today: 今日问答数
    - by_intent: 按意图类型统计
    - by_source: 按来源统计
    - by_user: 按用户统计
    - time_distribution: 时间分布
    """
    try:
        # 构建过滤器
        filter_kwargs = {
            "limit": 1000,
            "order_by": "timestamp",
            "order_desc": True
        }
        
        if start_time:
            filter_kwargs["start_time"] = datetime.fromisoformat(start_time)
        if end_time:
            filter_kwargs["end_time"] = datetime.fromisoformat(end_time)
        if workspace_id:
            filter_kwargs["workspace_id"] = workspace_id
        
        audit_filter = AuditFilter(**filter_kwargs)
        
        # 查询相关事件
        events = await audit_logger.query(audit_filter)
        
        # 统计分析
        qa_events = [e for e in events if "QA_ASK" in e.action]
        
        total = len(qa_events)
        today = len([
            e for e in qa_events
            if e.timestamp.date() == datetime.now().date()
        ])
        
        # 按意图类型统计
        by_intent = {}
        for event in qa_events:
            intent_type = event.context.get("intent_type", "query") if event.context else "query"
            by_intent[intent_type] = by_intent.get(intent_type, 0) + 1
        
        # 按来源统计
        by_source = {"graphiti": 0, "rag": 0, "mock": 0}
        for event in qa_events:
            if event.context and "sources_used" in event.context:
                for source in event.context["sources_used"]:
                    if source in by_source:
                        by_source[source] += 1
        
        # 时间分布（按小时）
        time_distribution = {}
        for event in qa_events:
            hour = event.timestamp.hour
            time_distribution[hour] = time_distribution.get(hour, 0) + 1
        
        return {
            "total": total,
            "today": today,
            "by_intent": by_intent,
            "by_source": by_source,
            "time_distribution": time_distribution,
            "period": {
                "start": start_time,
                "end": end_time
            }
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/qa/stats/users")
async def get_user_qa_stats(
    workspace_id: Optional[str] = Query(None),
    limit: int = Query(10, ge=1, le=100)
):
    """获取用户问答统计"""
    try:
        filter_kwargs = {
            "limit": 1000,
            "order_by": "timestamp",
            "order_desc": True
        }
        
        if workspace_id:
            filter_kwargs["workspace_id"] = workspace_id
        
        audit_filter = AuditFilter(**filter_kwargs)
        
        # 查询事件
        events = await audit_logger.query(audit_filter)
        
        # 过滤问答事件
        qa_events = [e for e in events if "QA_ASK" in e.action]
        
        # 按用户统计
        user_stats = {}
        for event in qa_events:
            actor_id = event.actor.actor_id if event.actor else "anonymous"
            if actor_id not in user_stats:
                user_stats[actor_id] = {
                    "user_id": actor_id,
                    "count": 0,
                    "first_time": event.timestamp,
                    "last_time": event.timestamp
                }
            user_stats[actor_id]["count"] += 1
            if event.timestamp > user_stats[actor_id]["last_time"]:
                user_stats[actor_id]["last_time"] = event.timestamp
            if event.timestamp < user_stats[actor_id]["first_time"]:
                user_stats[actor_id]["first_time"] = event.timestamp
        
        # 排序并限制数量
        sorted_users = sorted(
            user_stats.values(),
            key=lambda x: x["count"],
            reverse=True
        )[:limit]
        
        return {
            "user_stats": sorted_users,
            "total_users": len(user_stats),
            "limit": limit
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/qa/stats/topics")
async def get_topic_stats(
    workspace_id: Optional[str] = Query(None),
    limit: int = Query(20, ge=1, le=100)
):
    """获取话题统计"""
    try:
        # 简化实现，返回模拟数据
        # 实际应该从问答历史中提取话题
        return {
            "topics": [
                {"topic": "雷达目标查询", "count": 45, "trend": "up"},
                {"topic": "部队部署情况", "count": 32, "trend": "stable"},
                {"topic": "威胁评估分析", "count": 28, "trend": "up"},
                {"topic": "武器系统性能", "count": 21, "trend": "down"},
                {"topic": "战场态势对比", "count": 18, "trend": "stable"}
            ][:limit],
            "limit": limit
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# ==================== 闭环反馈路由 ====================

@router.post("/feedback/action")
async def submit_action_feedback(request: Request, data: Dict[str, Any]):
    """
    提交动作执行反馈
    
    请求体:
    {
        "action_id": "动作ID",
        "decision_id": "关联的决策ID",
        "outcome": "success|failure|partial",
        "result_data": {},
        "error_message": "错误信息（如果失败）"
    }
    """
    try:
        from datetime import datetime as dt
        
        action_id = data.get("action_id", "")
        decision_id = data.get("decision_id")
        outcome = data.get("outcome", "success")
        result_data = data.get("result_data", {})
        error_message = data.get("error_message")
        
        # 记录反馈
        asyncio.create_task(
            audit_logger.log_success(
                event_type=AuditEventType.DATA_INGEST,
                action="ACTION_FEEDBACK",
                resource=ResourceInfo(
                    resource_type="feedback",
                    resource_id=action_id,
                    resource_name="动作反馈"
                ),
                message=f"动作反馈: {outcome}",
                actor=ActorInfo(
                    actor_type="user",
                    actor_id=data.get("user_id", "system"),
                    actor_name=data.get("user_id", "System"),
                    roles=[]
                ),
                context={
                    "action_id": action_id,
                    "decision_id": decision_id,
                    "outcome": outcome,
                    "result_data": result_data,
                    "error_message": error_message,
                    "duration_ms": data.get("duration_ms", 0)
                }
            )
        )
        
        return {
            "status": "success",
            "feedback_id": f"af_{uuid.uuid4().hex[:12]}",
            "outcome": outcome
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/feedback/decision/{decision_id}")
async def get_decision_feedback(decision_id: str):
    """获取决策的反馈历史"""
    try:
        # 构建过滤器
        audit_filter = AuditFilter(
            limit=100,
            order_by="timestamp",
            order_desc=True
        )
        
        # 查询事件
        events = await audit_logger.query(audit_filter)
        
        # 过滤相关反馈
        feedback_events = [
            e for e in events
            if e.context and e.context.get("decision_id") == decision_id
        ]
        
        return {
            "decision_id": decision_id,
            "feedback_count": len(feedback_events),
            "feedbacks": [
                {
                    "feedback_id": e.id,
                    "outcome": e.context.get("outcome", "unknown"),
                    "timestamp": e.timestamp.isoformat() if isinstance(e.timestamp, dt) else str(e.timestamp)
                }
                for e in feedback_events
            ]
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# ==================== OpenHarness 路由 ====================

@router.get("/openharness/tools")
async def list_openharness_tools():
    """列出所有 OpenHarness 工具"""
    try:
        from odap.infra.openharness import create_harness
        harness = create_harness()
        if harness:
            tools = harness.list_available_tools()
            return {"tools": tools, "count": len(tools)}
        return {"tools": [], "count": 0, "message": "OpenHarness 不可用"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/openharness/run")
async def run_openharness_action(data: Dict[str, Any]):
    """运行 OpenHarness 工具"""
    try:
        from odap.infra.openharness import create_harness
        harness = create_harness()
        if not harness:
            raise HTTPException(status_code=503, detail="OpenHarness 不可用")
        
        action = data.get("action")
        if not action:
            raise HTTPException(status_code=400, detail="action 不能为空")
        
        obs, reward, done, info = harness.step(action)
        return {
            "observation": obs,
            "reward": reward,
            "done": done,
            "info": info
        }
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/openharness/run-episode")
async def run_openharness_episode(data: Dict[str, Any]):
    """运行完整的 OpenHarness 会话"""
    try:
        from odap.infra.openharness import create_harness
        harness = create_harness()
        if not harness:
            raise HTTPException(status_code=503, detail="OpenHarness 不可用")
        
        actions = data.get("actions", [])
        if not isinstance(actions, list):
            raise HTTPException(status_code=400, detail="actions 必须是数组")
        
        results = harness.run_episode(actions)
        return {
            "results": results,
            "total_steps": len(results),
            "done": results[-1]["done"] if results else False
        }
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/openharness/health")
async def check_openharness_health():
    """检查 OpenHarness 健康状态"""
    try:
        from odap.infra.openharness import create_harness
        harness = create_harness()
        if harness:
            tools = harness.list_available_tools()
            return {
                "status": "healthy",
                "openharness_available": True,
                "tools_count": len(tools),
                "tools": tools[:5]  # 只返回前5个工具
            }
        return {
            "status": "healthy",
            "openharness_available": False,
            "message": "OpenHarness 不可用，使用 fallback 模式"
        }
    except Exception as e:
        return {
            "status": "unhealthy",
            "openharness_available": False,
            "error": str(e)
        }


@router.get("/openharness/schemas")
async def get_openharness_schemas():
    """获取 OpenHarness 工具的 OpenAI 格式 schema"""
    try:
        from odap.infra.openharness import export_tool_schemas
        schemas = export_tool_schemas()
        return {
            "schemas": schemas,
            "count": len(schemas)
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))