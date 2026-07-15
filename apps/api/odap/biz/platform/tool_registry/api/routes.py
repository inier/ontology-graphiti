import logging
import uuid
from typing import Dict, Any, List, Optional
from pydantic import BaseModel, Field

from fastapi import APIRouter, HTTPException, Query, Depends
from odap.infra.security.jwt_auth import get_current_user

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/tools", tags=["tool_registry"])


class ToolRegisterRequest(BaseModel):
    name: str
    description: str
    tool_type: str = "function"
    category: str = "general"
    version: str = "1.0.0"
    danger_level: str = "low"
    capabilities: List[str] = Field(default_factory=list)
    input_schema: Optional[Dict[str, Any]] = None
    output_schema: Optional[Dict[str, Any]] = None
    semantic_tags: List[str] = Field(default_factory=list)
    opa_action: str = ""
    requires_opa_check: bool = False


class ToolInvokeRequest(BaseModel):
    params: Dict[str, Any] = Field(default_factory=dict)
    user: Optional[Dict[str, Any]] = None


class ToolDiscoverRequest(BaseModel):
    query: str
    top_k: int = 5


def _get_tool_registry():
    try:
        from odap.biz.platform.tool_registry import get_tool_registry
        return get_tool_registry()
    except HTTPException:
        raise
    except Exception:
        return None


@router.post("/register")
async def register_tool(request: ToolRegisterRequest,
    user=Depends(get_current_user)):
    registry = _get_tool_registry()
    if registry:
        try:
            def placeholder_func(**kwargs):
                return {"message": f"Tool {request.name} executed"}

            success = registry.register_function(
                name=request.name,
                description=request.description,
                func=placeholder_func,
                category=request.category,
            )
            return {"status": "success" if success else "error", "name": request.name}
        except HTTPException:
            raise
        except Exception as e:
            raise HTTPException(status_code=500, detail=str(e))

    return {"status": "error", "message": "No tool registry available"}


@router.delete("/{tool_id}")
async def unregister_tool(tool_id: str,
    user=Depends(get_current_user)):
    registry = _get_tool_registry()
    if registry:
        success = registry.unregister(tool_id)
        if success:
            return {"status": "success", "tool_id": tool_id}
        return {"status": "error", "message": f"Tool {tool_id} not found"}

    return {"status": "error", "message": "No tool registry available"}


@router.post("/{tool_id}/invoke")
async def invoke_tool(tool_id: str, request: ToolInvokeRequest,
    user=Depends(get_current_user)):
    registry = _get_tool_registry()
    if registry:
        try:
            exec_result = registry.execute(tool_id, request.params, request.user)
            return {
                "status": "success" if exec_result.success else "error",
                "tool_id": exec_result.tool_id,
                "result": exec_result.data,
                "error": exec_result.error,
            }
        except HTTPException:
            raise
        except Exception as e:
            raise HTTPException(status_code=500, detail=str(e))

    raise HTTPException(status_code=503, detail="No tool registry available")


@router.get("")
async def list_tools(category: Optional[str] = Query(None)):
    registry = _get_tool_registry()
    if registry:
        tools = registry.discover(category=category)
        return {"status": "success", "tools": tools, "count": len(tools)}

    return {"status": "success", "tools": [], "count": 0}


@router.post("/discover")
async def discover_tools(request: ToolDiscoverRequest,
    user=Depends(get_current_user)):
    registry = _get_tool_registry()
    if registry:
        try:
            tools = registry.discover(semantic_query=request.query)
            return {"status": "success", "tools": tools[:request.top_k], "count": len(tools)}
        except HTTPException:
            raise
        except Exception as e:
            raise HTTPException(status_code=500, detail=str(e))

    return {"status": "success", "tools": [], "count": 0}
