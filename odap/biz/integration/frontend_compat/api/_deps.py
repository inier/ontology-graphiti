"""前端API兼容层 - 共享依赖和工具函数"""

from fastapi import HTTPException, Request
from odap.infra.security.jwt_auth import get_current_user
from typing import Dict, Any, List, Optional
import json
import os
import uuid
import asyncio
from datetime import datetime
from odap.infra.security import (
    get_audit_logger, AuditFilter, AuditEventType, AuditSeverity,
    ActorInfo, ResourceInfo, ActionResult, audit_log,
)

# ── 场景存储目录 ──
_storage_base = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
_odap_root = os.path.dirname(os.path.dirname(_storage_base))
SCENARIOS_DIR = os.path.join(_odap_root, "storage", "versions", "scenarios")

# ── 外部服务实例 ──
from odap.biz.shared.stores import ScenarioStore
from odap.infra.graph.graph_service import GraphManager
from odap.biz.platform.workspace.services.workspace_service import WorkspaceService
from odap.biz.platform.workspace.services.scenario_service import ScenarioService


import logging

logger = logging.getLogger(__name__)
# 初始化存储
try:
    from odap.biz.platform.workspace.services.workspace_service import WorkspaceService as _WS
    storage = _WS().storage if hasattr(_WS(), 'storage') else None
except HTTPException:
    raise
except Exception as e:
    logger.info(f'Failed to initialize storage: {e}')
    storage = None

_graph_manager = None


def _get_graph_manager():
    global _graph_manager
    if _graph_manager is None:
        _graph_manager = GraphManager()
    return _graph_manager


scenario_store = ScenarioStore(storage_dir=SCENARIOS_DIR, graph_manager=None)
workspace_service = WorkspaceService()

# 初始化审计日志器
audit_logger = get_audit_logger()


# ── 本地审计日志装饰器 ──

def local_audit_log(action: str, resource: str):
    """本地审计日志装饰器"""
    def decorator(func):
        async def wrapper(*args, **kwargs):
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
                from odap.infra.security import audit_info, AuditEventType
                audit_info(
                    event_type=AuditEventType.SYSTEM_HEALTH,
                    actor={"type": "user", "id": "system", "name": "System"},
                    action=action,
                    resource={"type": resource, "id": resource, "name": resource},
                    result={"status": "success"},
                    workspace_id="system",
                )
                return result
            except HTTPException:
                raise
            except Exception as e:
                from odap.infra.security import audit_error, AuditEventType
                audit_error(
                    event_type=AuditEventType.SYSTEM_ERROR,
                    actor={"type": "user", "id": "system", "name": "System"},
                    action=action,
                    resource={"type": resource, "id": resource, "name": resource},
                    result={"status": "error", "error": str(e)},
                    workspace_id="system",
                )
                raise
        return wrapper
    return decorator


# ── 审计日志辅助函数 ──

def log_ingest(ingest_type: str, **kwargs):
    """记录数据摄入日志"""
    asyncio.create_task(
        audit_logger.log_success(
            event_type=AuditEventType.DATA_INGEST,
            action=f"INGEST_{ingest_type.upper()}",
            resource=ResourceInfo(
                resource_type="data",
                resource_id=ingest_type,
                resource_name=ingest_type,
            ),
            message=f"Data ingest {ingest_type} completed",
            actor=ActorInfo(
                actor_type="user",
                actor_id=kwargs.get("user", "system"),
                actor_name=kwargs.get("user", "System"),
                roles=[],
            ),
            context={
                "filename": kwargs.get("filename"),
                "count": kwargs.get("count"),
            },
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
                resource_name="Query",
            ),
            message=f"Query completed with {result_count} results",
            actor=ActorInfo(
                actor_type="user",
                actor_id=kwargs.get("user", "system"),
                actor_name=kwargs.get("user", "System"),
                roles=[],
            ),
            context={
                "query": query,
                "result_count": result_count,
            },
        )
    )


def log_error(error: str, **kwargs):
    """记录错误日志"""
    import logging
    context = kwargs.get("context", "")
    logging.getLogger("frontend_compat").error(f"[{context}] {error}" if context else error)
    try:
        asyncio.create_task(
            audit_logger.log_error(
                event_type=AuditEventType.SYSTEM_ERROR,
                action="ERROR",
                resource=ResourceInfo(
                    resource_type="error",
                    resource_id=kwargs.get("context", "unknown"),
                    resource_name=kwargs.get("context", "Error"),
                ),
                message=error,
                actor=ActorInfo(
                    actor_type="system",
                    actor_id="system",
                    actor_name="System",
                    roles=[],
                ),
                context=kwargs,
            )
        )
    except HTTPException:
        raise
    except Exception:
        pass


async def _log_error_async(error: str, context: Dict[str, Any]):
    """异步记录错误日志"""
    import logging
    logging.getLogger("frontend_compat").error(f"[{context}] {error}")
    try:
        await audit_logger.log_error(
            event_type=AuditEventType.SYSTEM_ERROR,
            action="ERROR",
            resource=ResourceInfo(
                resource_type="error",
                resource_id=context.get("source", "unknown"),
                resource_name="Error",
            ),
            message=error,
            actor=ActorInfo(
                actor_type="system",
                actor_id="system",
                actor_name="System",
                roles=[],
            ),
            context=context,
        )
    except HTTPException:
        raise
    except Exception:
        pass


# ── QA Engine 全局实例 ──

_qa_engine_instance = None


def get_qa_engine(use_mock: bool = False) -> "QAEngineV2":
    """获取全局 QAEngineV2 实例"""
    global _qa_engine_instance
    if _qa_engine_instance is None:
        from odap.biz.data.qa.qa_engine import QAEngineV2

        graphiti_client = _get_graph_manager()

        ingest_storage = None
        try:
            from odap.biz.core.ontology.design.services.ingest_service import IngestService
            ingest_storage = IngestService().storage
        except HTTPException:
            raise
        except Exception:
            pass

        semantic_map_storage = None
        try:
            from odap.biz.data.semantic_map.services.semantic_map_service import SemanticMapService


            semantic_map_storage = SemanticMapService().storage
        except HTTPException:
            raise
        except Exception:
            pass

        _qa_engine_instance = QAEngineV2(
            graphiti_client=graphiti_client,
            use_mock=use_mock,
            ingest_storage=ingest_storage,
            semantic_map_storage=semantic_map_storage,
        )
    return _qa_engine_instance
