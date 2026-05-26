"""MCP服务"""

from typing import Dict, Any, List
from ..impl.server_manager import ToolServerManager
from ..impl.connection_pool import ConnectionPoolManager


class MCPService:
    """MCP服务"""
    
    def __init__(self):
        self.server_manager = ToolServerManager()
        self.pool_manager = ConnectionPoolManager()
    
    def register_server(self, name: str, url: str, description: str = "") -> Dict[str, Any]:
        """注册服务器"""
        server = self.server_manager.register_server(name, url, description)
        self.pool_manager.create_pool(server.id)
        
        return {
            "server_id": server.id,
            "name": server.name,
            "url": server.url,
            "status": server.status.value
        }
    
    def connect_server(self, server_id: str) -> Dict[str, Any]:
        """连接服务器"""
        success = self.server_manager.connect_server(server_id)
        return {"status": "success" if success else "error"}
    
    def disconnect_server(self, server_id: str) -> Dict[str, Any]:
        """断开服务器连接"""
        success = self.server_manager.disconnect_server(server_id)
        return {"status": "success" if success else "error"}
    
    def list_servers(self, status: str = None) -> List[Dict[str, Any]]:
        """列出服务器"""
        filters = {"status": status} if status else None
        servers = self.server_manager.list_servers(filters)
        
        return [
            {
                "server_id": s.id,
                "name": s.name,
                "url": s.url,
                "status": s.status.value
            }
            for s in servers
        ]
    
    def discover_tools(self, server_id: str) -> List[Dict[str, Any]]:
        """发现工具"""
        return self.server_manager.discover_tools(server_id)
    
    def acquire_connection(self, server_id: str) -> Dict[str, Any]:
        """获取连接"""
        conn_id = self.pool_manager.acquire(server_id)
        if conn_id:
            return {"connection_id": conn_id, "status": "acquired"}
        return {"status": "error", "message": "No connection available"}
    
    def release_connection(self, connection_id: str) -> Dict[str, Any]:
        """释放连接"""
        success = self.pool_manager.release(connection_id)
        return {"status": "success" if success else "error"}
    
    def get_pool_status(self, server_id: str) -> Dict[str, Any]:
        """获取连接池状态"""
        return self.pool_manager.get_pool_status(server_id)
