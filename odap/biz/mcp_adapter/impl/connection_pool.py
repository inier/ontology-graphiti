"""连接池实现"""

from typing import Dict, Any, Optional
from ..interfaces.connection_pool import IConnectionPool
from ..models.connection import Connection, ConnectionPool


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
        return pool
    
    def acquire(self, server_id: str) -> Optional[str]:
        """获取连接"""
        pool = self._pools.get(server_id)
        if not pool:
            return None
        
        if pool.acquired_connections >= pool.max_connections:
            return None
        
        connection = Connection(server_id=server_id)
        self._connections[connection.id] = connection
        
        pool.acquired_connections += 1
        pool.current_connections += 1
        
        return connection.id
    
    def release(self, connection_id: str) -> bool:
        """释放连接"""
        connection = self._connections.get(connection_id)
        if not connection:
            return False
        
        pool = self._pools.get(connection.server_id)
        if pool:
            pool.acquired_connections -= 1
        
        del self._connections[connection_id]
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
