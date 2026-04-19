"""Tool Server管理器实现"""

from typing import Dict, Any, List, Optional
from datetime import datetime
from ..interfaces.server_manager import IToolServerManager
from ..models.tool_server import ToolServer, ServerStatus, ServerCapability


class ToolServerManager(IToolServerManager):
    """Tool Server管理器实现"""
    
    def __init__(self):
        self._servers: Dict[str, ToolServer] = {}
    
    def register_server(self, name: str, url: str, description: str = "") -> ToolServer:
        """注册服务器"""
        server = ToolServer(
            name=name,
            url=url,
            description=description
        )
        self._servers[server.id] = server
        return server
    
    def get_server(self, server_id: str) -> Optional[ToolServer]:
        """获取服务器"""
        return self._servers.get(server_id)
    
    def unregister_server(self, server_id: str) -> bool:
        """取消注册服务器"""
        if server_id in self._servers:
            del self._servers[server_id]
            return True
        return False
    
    def connect_server(self, server_id: str) -> bool:
        """连接服务器"""
        server = self._servers.get(server_id)
        if not server:
            return False
        
        server.status = ServerStatus.CONNECTED
        server.connected_at = datetime.now()
        return True
    
    def disconnect_server(self, server_id: str) -> bool:
        """断开服务器连接"""
        server = self._servers.get(server_id)
        if not server:
            return False
        
        server.status = ServerStatus.DISCONNECTED
        server.connected_at = None
        return True
    
    def list_servers(self, filters: Dict[str, Any] = None) -> List[ToolServer]:
        """列出服务器"""
        filters = filters or {}
        servers = list(self._servers.values())
        
        if "status" in filters:
            servers = [s for s in servers if s.status.value == filters["status"]]
        
        return servers
    
    def discover_tools(self, server_id: str) -> List[Dict[str, Any]]:
        """发现工具"""
        server = self._servers.get(server_id)
        if not server:
            return []
        
        # 模拟工具发现
        return [
            {
                "name": f"tool_{i}",
                "description": f"Tool {i}",
                "parameters": {}
            }
            for i in range(3)
        ]
