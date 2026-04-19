"""MCP适配器数据模型"""

from .tool_server import ToolServer, ServerStatus, ServerCapability
from .connection import Connection, ConnectionPool

__all__ = [
    "ToolServer",
    "ServerStatus",
    "ServerCapability",
    "Connection",
    "ConnectionPool"
]
