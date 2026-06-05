"""API路由"""

from fastapi import APIRouter, HTTPException, Depends
from odap.infra.security.jwt_auth import get_current_user
from pydantic import BaseModel, Field
from typing import Dict, Any, List, Optional
from ..services.mcp_service import MCPService

router = APIRouter(prefix="/api/mcp", tags=["mcp"])

mcp_service = MCPService()


class RegisterServerRequest(BaseModel):
    name: str
    url: str
    description: str = ""


class CallToolRequest(BaseModel):
    arguments: Dict[str, Any] = Field(default_factory=dict)


@router.post("/servers")
async def register_server(request: RegisterServerRequest,
    user=Depends(get_current_user)):
    try:
        return mcp_service.register_server(request.name, request.url, request.description)
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.delete("/servers/{server_id}")
async def unregister_server(server_id: str,
    user=Depends(get_current_user)):
    try:
        result = mcp_service.unregister_server(server_id)
        if result.get("status") == "error":
            raise HTTPException(status_code=404, detail=result.get("message", "Server not found"))
        return result
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/servers/{server_id}/connect")
async def connect_server(server_id: str,
    user=Depends(get_current_user)):
    try:
        return mcp_service.connect_server(server_id)
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/servers/{server_id}/disconnect")
async def disconnect_server(server_id: str,
    user=Depends(get_current_user)):
    try:
        return mcp_service.disconnect_server(server_id)
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/servers")
async def list_servers(status: Optional[str] = None,
    user=Depends(get_current_user)):
    try:
        return {"servers": mcp_service.list_servers(status)}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/servers/{server_id}/tools")
async def discover_tools(server_id: str,
    user=Depends(get_current_user)):
    try:
        return {"tools": mcp_service.discover_tools(server_id)}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/servers/{server_id}/tools/{tool_name}")
async def call_tool(server_id: str, tool_name: str, request: CallToolRequest,
    user=Depends(get_current_user)):
    try:
        result = await mcp_service.call_tool(server_id, tool_name, request.arguments)
        if result.get("status") == "error":
            raise HTTPException(status_code=400, detail=result.get("message", "Tool call failed"))
        return result
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/servers/{server_id}/status")
async def get_server_status(server_id: str,
    user=Depends(get_current_user)):
    try:
        result = mcp_service.get_server_status(server_id)
        if result.get("status") == "error":
            raise HTTPException(status_code=404, detail=result.get("message", "Server not found"))
        return result
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/servers/{server_id}/pool-status")
async def get_pool_status(server_id: str,
    user=Depends(get_current_user)):
    try:
        return mcp_service.get_pool_status(server_id)
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
