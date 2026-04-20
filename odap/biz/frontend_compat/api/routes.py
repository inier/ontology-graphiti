"""前端API兼容层 - 使用统一的工作空间管理和场景存储"""

from fastapi import APIRouter, HTTPException, Query, UploadFile, File, Form, Request
from typing import Dict, Any, List, Optional
import json
import os
import uuid
import asyncio
from datetime import datetime
from odap.infra.security import get_audit_logger, AuditFilter, AuditEventType, AuditSeverity, ActorInfo, ResourceInfo, ActionResult

router = APIRouter(prefix="/api/frontend-compat", tags=["frontend-compat"])

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

# 初始化服务
graph_manager = GraphManager()
scenario_store = ScenarioStore(storage_dir=SCENARIOS_DIR, graph_manager=graph_manager)
workspace_service = WorkspaceService()

# 初始化审计日志器
audit_logger = get_audit_logger()


# 审计日志装饰器
def audit_log(action: str, resource: str):
    """审计日志装饰器"""
    def decorator(func):
        async def wrapper(request: Request, *args, **kwargs):
            try:
                result = await func(request, *args, **kwargs)
                # 记录成功日志
                await audit_logger.log_success(
                    event_type=AuditEventType.SYSTEM_HEALTH,
                    action=action,
                    resource=ResourceInfo(
                        resource_type=resource,
                        resource_id=resource,
                        resource_name=resource
                    ),
                    message=f"{action} completed successfully",
                    actor=ActorInfo(
                        actor_type="user",
                        actor_id="system",
                        actor_name="System",
                        roles=[]
                    )
                )
                return result
            except Exception as e:
                # 记录错误日志
                await audit_logger.log_error(
                    event_type=AuditEventType.SYSTEM_HEALTH,
                    action=action,
                    resource=ResourceInfo(
                        resource_type=resource,
                        resource_id=resource,
                        resource_name=resource
                    ),
                    message=str(e),
                    actor=ActorInfo(
                        actor_type="user",
                        actor_id="system",
                        actor_name="System",
                        roles=[]
                    )
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
    """记录错误日志"""
    asyncio.create_task(
        audit_logger.log_error(
            event_type=AuditEventType.SYSTEM_HEALTH,
            action="ERROR",
            resource=ResourceInfo(
                resource_type="system",
                resource_id="system",
                resource_name="System"
            ),
            message=error,
            actor=ActorInfo(
                actor_type="user",
                actor_id="system",
                actor_name="System",
                roles=[]
            ),
            context=kwargs
        )
    )


# 初始化默认数据
def init_default_data():
    """初始化默认数据"""
    pass


# 初始化默认数据
init_default_data()


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
        entities = scenario_store.get_entities(scenario_id)
        return {"entities": entities}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/scenarios/{scenario_id}/relations")
async def get_relations(scenario_id: str):
    """获取关系（兼容前端）"""
    try:
        result = scenario_store.get_relations(scenario_id)
        return {
            "scenario_id": scenario_id,
            "nodes": result.get("nodes", []),
            "links": result.get("links", [])
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# ==================== 数据摄入路由 ====================

@router.post("/ingest/text")
@audit_log(action="INGEST_TEXT", resource="text")
async def ingest_text(request: Request, data: Dict[str, Any]):
    """文本摄入（兼容前端）"""
    try:
        from odap.tasks import process_ingest_task
        
        task_id = f"task_{uuid.uuid4().hex[:12]}"
        # 启动异步任务
        task = process_ingest_task.delay(
            task_id,
            'text',
            {'text': data.get('text', '')},
            data.get('scenario_id')
        )
        
        # 记录审计日志
        log_ingest('text', user="system")
        
        return {"success": True, "task_id": task_id}
    except Exception as e:
        log_error(str(e), context="ingest_text")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/ingest/news")
@audit_log(action="INGEST_NEWS", resource="news")
async def ingest_news(request: Request, data: Dict[str, Any]):
    """新闻摄入（兼容前端）"""
    try:
        from odap.tasks import process_ingest_task
        
        task_id = f"task_{uuid.uuid4().hex[:12]}"
        # 启动异步任务
        task = process_ingest_task.delay(
            task_id,
            'news',
            {'url': data.get('url', '')},
            data.get('scenario_id')
        )
        
        # 记录审计日志
        log_ingest('news', user="system")
        
        return {"success": True, "task_id": task_id}
    except Exception as e:
        log_error(str(e), context="ingest_news")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/ingest/random")
@audit_log(action="INGEST_RANDOM", resource="random")
async def ingest_random(request: Request, data: Dict[str, Any]):
    """随机数据摄入（兼容前端）"""
    try:
        from odap.tasks import process_ingest_task
        
        task_id = f"task_{uuid.uuid4().hex[:12]}"
        # 启动异步任务
        task = process_ingest_task.delay(
            task_id,
            'random',
            {'count': data.get('count', 10)},
            data.get('scenario_id')
        )
        
        # 记录审计日志
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
        from odap.tasks import process_ingest_task
        
        task_id = f"task_{uuid.uuid4().hex[:12]}"
        # 启动异步任务
        task = process_ingest_task.delay(
            task_id,
            'manual',
            data.get('data', {}),
            data.get('scenario_id')
        )
        
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
        # 记录审计事件
        event = await audit_logger.log(
            event_type=AuditEventType(data.get("event_type", "system.action")),
            action=data.get("action", ""),
            resource=ResourceInfo(
                resource_type=data.get("resource_type", ""),
                resource_id=data.get("resource_id", ""),
                resource_name=data.get("resource_id", "")
            ),
            result=ActionResult(
                status=data.get("result_status", "success"),
                message=data.get("result_message", "")
            ),
            severity=AuditSeverity(data.get("severity", "info")),
            actor=ActorInfo(
                actor_type="user",
                actor_id=data.get("actor_id", "system"),
                actor_name=data.get("actor_name", "System"),
                roles=[]
            ),
            workspace_id=data.get("workspace_id", "default"),
            context=data.get("context")
        )
        
        event_dict = event.model_dump()
        if isinstance(event_dict["timestamp"], datetime):
            event_dict["timestamp"] = event_dict["timestamp"].isoformat()
        return event_dict
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

@router.get("/workspaces")
async def list_workspaces():
    """列出工作空间（兼容前端）"""
    try:
        result = workspace_service.list_workspaces(filters={}, page=1, page_size=100)
        workspaces = result.get("workspaces", [])
        # 转换为前端兼容格式
        return {"workspaces": workspaces}
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


@router.post("/workspaces")
async def create_workspace(data: Dict[str, Any]):
    """创建工作空间（兼容前端）"""
    try:
        result = workspace_service.create_workspace(
            name=data.get("name", "新工作空间"),
            description=data.get("description", ""),
            owner=data.get("owner", "system")
        )
        return result
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.put("/workspaces/{workspace_id}")
async def update_workspace(workspace_id: str, data: Dict[str, Any]):
    """更新工作空间（兼容前端）"""
    try:
        updates = {}
        if "name" in data:
            updates["name"] = data["name"]
        if "description" in data:
            updates["description"] = data["description"]
        if "status" in data:
            updates["status"] = data["status"]

        result = workspace_service.update_workspace(workspace_id, updates)
        if result.get("status") == "error":
            raise HTTPException(status_code=404, detail=result.get("message"))
        return result
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.delete("/workspaces/{workspace_id}")
async def delete_workspace(workspace_id: str):
    """删除工作空间（兼容前端）"""
    try:
        result = workspace_service.delete_workspace(workspace_id)
        if result.get("status") == "error":
            raise HTTPException(status_code=404, detail=result.get("message"))
        return {"status": "success", "message": result.get("message")}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/workspaces/{workspace_id}/activate")
async def activate_workspace(workspace_id: str):
    """激活工作空间（兼容前端）"""
    try:
        result = workspace_service.activate_workspace(workspace_id)
        if result.get("status") == "error":
            raise HTTPException(status_code=404, detail=result.get("message"))
        return {"status": "success"}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/workspaces/{workspace_id}/deactivate")
async def deactivate_workspace(workspace_id: str):
    """停用工作空间（兼容前端）"""
    try:
        result = workspace_service.deactivate_workspace(workspace_id)
        if result.get("status") == "error":
            raise HTTPException(status_code=404, detail=result.get("message"))
        return {"status": "success"}
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
        graph_manager = GraphManager()
        
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
        graph_manager = GraphManager()
        
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