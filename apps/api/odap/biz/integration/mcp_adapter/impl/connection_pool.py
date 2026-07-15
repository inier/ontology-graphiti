"""连接池实现"""

import logging
from typing import Dict, Any, Optional
from ..interfaces.connection_pool import IConnectionPool
from ..models.connection import Connection, ConnectionPool

logger = logging.getLogger(__name__)

# ── 审计工具（懒加载 + 容错） ──
def _mcp_pool_audit(action: str, *, result_status: str = "success",
                    result_message: str = "", resource: str = None,
                    details: Dict[str, Any] = None) -> None:
    try:
        from odap.infra.security.audit_helper import storage_audit
        storage_audit(
            action=action,
            result_status=result_status,
            result_message=result_message,
            resource=resource,
            details=details or {},
            service="integration_mcp",
        )
    except Exception as e:
        logger.warning(f"audit failed: {e}")


class ConnectionPoolManager(IConnectionPool):
    """连接池管理器实现"""

    def __init__(self):
        self._pools: Dict[str, ConnectionPool] = {}
        self._connections: Dict[str, Connection] = {}

    def create_pool(self, server_id: str, max_connections: int = 10,
                   min_connections: int = 2) -> ConnectionPool:
        """创建连接池"""
        pool = ConnectionPool(
            server_id=server_id,
            max_connections=max_connections,
            min_connections=min_connections
        )
        self._pools[server_id] = pool
        _mcp_pool_audit(
            action="mcp_conn_pool_create",
            result_status="success",
            resource=server_id,
            details={
                "mcp_server_id": server_id,
                "max_connections": max_connections,
                "min_connections": min_connections,
            },
        )
        return pool

    def acquire(self, server_id: str) -> Optional[str]:
        """获取连接"""
        pool = self._pools.get(server_id)
        if not pool:
            _mcp_pool_audit(
                action="mcp_conn_acquire",
                result_status="failure",
                result_message="Pool not found",
                resource=server_id,
                details={"mcp_server_id": server_id},
            )
            return None

        if pool.acquired_connections >= pool.max_connections:
            _mcp_pool_audit(
                action="mcp_conn_acquire",
                result_status="failure",
                result_message="Pool exhausted",
                resource=server_id,
                details={
                    "mcp_server_id": server_id,
                    "acquired": pool.acquired_connections,
                    "max": pool.max_connections,
                },
            )
            return None

        connection = Connection(server_id=server_id)
        self._connections[connection.id] = connection

        pool.acquired_connections += 1
        pool.current_connections += 1

        _mcp_pool_audit(
            action="mcp_conn_acquire",
            result_status="success",
            resource=connection.id,
            details={
                "mcp_server_id": server_id,
                "connection_id": connection.id,
                "acquired_count": pool.acquired_connections,
            },
        )
        return connection.id

    def release(self, connection_id: str) -> bool:
        """释放连接"""
        connection = self._connections.get(connection_id)
        if not connection:
            _mcp_pool_audit(
                action="mcp_conn_release",
                result_status="failure",
                result_message="Connection not found",
                resource=connection_id,
                details={"connection_id": connection_id},
            )
            return False

        pool = self._pools.get(connection.server_id)
        acquired_after = 0
        if pool:
            pool.acquired_connections -= 1
            acquired_after = pool.acquired_connections

        del self._connections[connection_id]

        _mcp_pool_audit(
            action="mcp_conn_release",
            result_status="success",
            resource=connection_id,
            details={
                "connection_id": connection_id,
                "mcp_server_id": connection.server_id,
                "acquired_after": acquired_after,
            },
        )
        return True
    
    def get_pool_status(self, server_id: str) -> Dict[str, Any]:
        """获取连接池状态"""
        pool = self._pools.get(server_id)
        if not pool:
            return {"status": "not_found"}
        
        return {
            "server_id": pool.server_id,
            "max_connections": pool.max_connections,
            "min_connections": pool.min_connections,
            "current_connections": pool.current_connections,
            "acquired_connections": pool.acquired_connections
        }
