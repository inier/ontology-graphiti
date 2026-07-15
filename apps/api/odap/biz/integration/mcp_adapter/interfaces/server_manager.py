"""Tool Server管理器接口"""

from typing import Dict, Any, List, Optional
from ..models.tool_server import ToolServer, ServerStatus


class IToolServerManager:
    """Tool Server管理器接口"""

    def register_server(self, name: str, url: str, description: str = "") -> ToolServer:
        """注册服务器"""
        raise NotImplementedError

    def get_server(self, server_id: str) -> Optional[ToolServer]:
        """获取服务器"""
        raise NotImplementedError

    def unregister_server(self, server_id: str) -> bool:
        """取消注册服务器"""
        raise NotImplementedError

    def connect_server(self, server_id: str) -> bool:
        """连接服务器"""
        raise NotImplementedError

    def disconnect_server(self, server_id: str) -> bool:
        """断开服务器连接"""
        raise NotImplementedError

    def list_servers(self, filters: Dict[str, Any] = None) -> List[ToolServer]:
        """列出服务器"""
        raise NotImplementedError

    def discover_tools(self, server_id: str) -> List[Dict[str, Any]]:
        """发现工具"""
        raise NotImplementedError
