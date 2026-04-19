"""MCP适配器接口"""

from .server_manager import IToolServerManager
from .connection_pool import IConnectionPool

__all__ = [
    "IToolServerManager",
    "IConnectionPool"
]
