"""API路由"""

from fastapi import APIRouter, HTTPException
from typing import Dict, Any, List, Optional
from ..services.mcp_service import MCPService

router = APIRouter(prefix="/api/mcp", tags=["mcp"])

mcp_service = MCPService()


@router.post("/servers")
async def register_server(name: str, url: str, description: str = ""):
    """注册服务器"""
    try:
        return mcp_service.register_server(name, url, description)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/servers/{server_id}/connect")
async def connect_server(server_id: str):
    """连接服务器"""
    try:
        return mcp_service.connect_server(server_id)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/servers/{server_id}/disconnect")
async def disconnect_server(server_id: str):
    """断开服务器连接"""
    try:
        return mcp_service.disconnect_server(server_id)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/servers")
async def list_servers(status: Optional[str] = None):
    """列出服务器"""
    try:
        return {"servers": mcp_service.list_servers(status)}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/servers/{server_id}/tools")
async def discover_tools(server_id: str):
    """发现工具"""
    try:
        return {"tools": mcp_service.discover_tools(server_id)}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/servers/{server_id}/pool-status")
async def get_pool_status(server_id: str):
    """获取连接池状态"""
    try:
        return mcp_service.get_pool_status(server_id)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
