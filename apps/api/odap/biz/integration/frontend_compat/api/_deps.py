"""前端API兼容层 - 共享依赖和工具函数

仅保留当前 compat 路由实际使用的依赖。
已删除的模块对应依赖:
  - get_qa_engine()      → qa_routes.py 已删除，前端直接用 /api/qa/
  - workspace_service    → workspace_routes.py 已删除，前端直接用 /api/workspaces/
"""

from fastapi import HTTPException
import os
import asyncio
from odap.infra.security import (
    get_audit_logger, AuditEventType, ActorInfo, ResourceInfo,
)

_storage_base = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
_odap_root = os.path.dirname(os.path.dirname(_storage_base))
SCENARIOS_DIR = os.path.join(_odap_root, "storage", "versions", "scenarios")

from odap.infra.storage.scenario_store import ScenarioStore
from odap.infra.query import get_graph_write_proxy, get_query_service


import logging

logger = logging.getLogger(__name__)
try:
    from odap.biz.platform.workspace.services.workspace_service import WorkspaceService as _WS
    storage = _WS().storage if hasattr(_WS(), 'storage') else None
except HTTPException:
    raise
except Exception as e:
    logger.info(f'Failed to initialize storage: {e}')
    storage = None

def _get_graph_write_proxy():
    return get_graph_write_proxy()


def _get_query_service():
    return get_query_service()


scenario_store = ScenarioStore(storage_dir=SCENARIOS_DIR, graph_manager=None)

audit_logger = get_audit_logger()


def local_audit_log(action: str, resource: str):
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


def log_ingest(ingest_type: str, **kwargs):
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
    except Exception as exc:
        logger.debug("Non-critical error in audit access log: %s", exc)
