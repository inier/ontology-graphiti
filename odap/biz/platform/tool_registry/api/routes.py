"""
工具注册表 API 路由
提供工具注册、发现、执行的 REST API
"""

from fastapi import APIRouter, HTTPException, Depends, Query, Body
from pydantic import BaseModel, Field
from typing import Dict, Any, List, Optional
from datetime import datetime

router = APIRouter(prefix="/api/v1/tools", tags=["tool_registry"])


class ToolRegisterRequest(BaseModel):
    """工具注册请求"""
    name: str
    description: str
    tool_type: str
    category: str
    version: str = "1.0.0"
    danger_level: str = "low"
    capabilities: List[str] = []
    input_schema: Optional[Dict[str, Any]] = None
    output_schema: Optional[Dict[str, Any]] = None
    semantic_tags: List[str] = []
    opa_action: str = ""
    requires_opa_check: bool = False


class ToolExecuteRequest(BaseModel):
    """工具执行请求"""
    tool_name: str
    input_data: Dict[str, Any] = {}
    user: Optional[Dict[str, Any]] = None


class ToolChainCreateRequest(BaseModel):
    """工具链创建请求"""
    chain_id: str
    name: str
    description: str
    steps: List[Dict[str, Any]]


class ToolResponse(BaseModel):
    """工具响应"""
    tool_id: str
    name: str
    description: str
    tool_type: str
    category: str
    version: str
    status: str
    health: str
    call_count: int


class ExecutionResponse(BaseModel):
    """执行响应"""
    tool_id: str
    tool_name: str
    success: bool
    data: Any
    error: Optional[str]
    execution_time_ms: float
    timestamp: str


def get_registry():
    """获取工具注册表"""
    from odap.biz.platform.tool_registry import get_tool_registry
    return get_tool_registry()


@router.post("/register", response_model=Dict[str, Any])
async def register_tool(request: ToolRegisterRequest):
    """注册工具"""
    registry = get_registry()

    success = False
    if request.tool_type == "skill":
        try:
            from odap.tools.base import BaseSkill, SkillInput, SkillOutput, SkillMetadata

            class DynamicSkill(BaseSkill):
                metadata = SkillMetadata(
                    name=request.name,
                    description=request.description,
                    category=request.category,
                    version=request.version,
                    danger_level=request.danger_level,
                    requires_opa_check=request.requires_opa_check,
                    opa_action=request.opa_action,
                )

                def execute(self, input_data: SkillInput) -> SkillOutput:
                    return SkillOutput(
                        success=True,
                        data={"message": f"Skill {self.metadata.name} executed"},
                        execution_time_ms=0,
                        skill_name=self.metadata.name,
                        request_id=input_data.request_id,
                    )

            success = registry.register_skill(DynamicSkill(), version=request.version)
        except Exception:
            success = False
    elif request.tool_type == "rest":
        success = registry.register_rest_api(
            name=request.name,
            description=request.description,
            endpoint=request.input_schema.get("endpoint", "") if request.input_schema else "",
            method=request.input_schema.get("method", "POST") if request.input_schema else "POST",
            category=request.category
        )
    elif request.tool_type == "function":
        try:
            def placeholder_func(**kwargs):
                return {"message": f"Function {request.name} executed"}

            success = registry.register_function(
                name=request.name,
                description=request.description,
                func=placeholder_func,
                category=request.category
            )
        except Exception:
            success = False

    return {
        "success": success,
        "message": "Tool registered successfully" if success else "Failed to register tool",
        "tool_name": request.name
    }


@router.get("/discover", response_model=List[ToolResponse])
async def discover_tools(
    pattern: Optional[str] = Query(None),
    tool_type: Optional[str] = Query(None),
    category: Optional[str] = Query(None),
    capability: Optional[str] = Query(None),
    semantic_query: Optional[str] = Query(None)
):
    """发现工具"""
    registry = get_registry()

    tools = registry.discover(
        pattern=pattern,
        tool_type=tool_type,
        category=category,
        capability=capability,
        semantic_query=semantic_query
    )

    return [ToolResponse(**tool) for tool in tools]


@router.post("/execute", response_model=ExecutionResponse)
async def execute_tool(request: ToolExecuteRequest):
    """执行工具"""
    registry = get_registry()

    result = registry.execute(
        tool_name=request.tool_name,
        input_data=request.input_data,
        user=request.user
    )

    return ExecutionResponse(
        tool_id=result.tool_id,
        tool_name=result.tool_name,
        success=result.success,
        data=result.data,
        error=result.error,
        execution_time_ms=result.execution_time_ms,
        timestamp=result.timestamp
    )


@router.post("/chain/register")
async def register_tool_chain(request: ToolChainCreateRequest):
    """注册工具链"""
    from odap.biz.platform.tool_registry.registry import ToolChain, ToolChainStep

    registry = get_registry()

    steps = [ToolChainStep(**step) for step in request.steps]
    chain = ToolChain(
        chain_id=request.chain_id,
        name=request.name,
        description=request.description,
        steps=steps
    )

    success = registry.register_tool_chain(chain)

    return {
        "success": success,
        "chain_id": request.chain_id,
        "message": "Tool chain registered successfully" if success else "Failed to register tool chain"
    }


@router.post("/chain/{chain_id}/execute")
async def execute_tool_chain(
    chain_id: str,
    initial_input: Dict[str, Any] = Body(...),
    user: Optional[Dict[str, Any]] = Body(None)
):
    """执行工具链"""
    registry = get_registry()

    try:
        results = registry.execute_chain(chain_id, initial_input, user)
        return {
            "chain_id": chain_id,
            "success": all(r.success for r in results),
            "steps": len(results),
            "results": [
                {
                    "tool_name": r.tool_name,
                    "success": r.success,
                    "data": r.data,
                    "error": r.error
                }
                for r in results
            ]
        }
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))


@router.get("/chain/{chain_id}")
async def get_tool_chain(chain_id: str):
    """获取工具链"""
    registry = get_registry()
    chain = registry.get_tool_chain(chain_id)

    if not chain:
        raise HTTPException(status_code=404, detail=f"Tool chain not found: {chain_id}")

    return {
        "chain_id": chain.chain_id,
        "name": chain.name,
        "description": chain.description,
        "steps": len(chain.steps),
        "enabled": chain.enabled
    }


@router.get("/chains")
async def list_tool_chains():
    """列出所有工具链"""
    registry = get_registry()
    chains = registry.list_tool_chains()

    return {
        "count": len(chains),
        "chains": [
            {
                "chain_id": c.chain_id,
                "name": c.name,
                "description": c.description,
                "step_count": len(c.steps),
                "enabled": c.enabled
            }
            for c in chains
        ]
    }


@router.get("/health")
async def get_health_report():
    """获取健康报告"""
    registry = get_registry()
    return registry.get_health_report()


@router.get("/history")
async def get_execution_history(limit: int = Query(100, ge=1, le=1000)):
    """获取执行历史"""
    registry = get_registry()
    history = registry.get_execution_history(limit)

    return {
        "count": len(history),
        "executions": [
            {
                "tool_id": r.tool_id,
                "tool_name": r.tool_name,
                "success": r.success,
                "execution_time_ms": r.execution_time_ms,
                "timestamp": r.timestamp
            }
            for r in history
        ]
    }


@router.get("/{tool_name}")
async def get_tool(tool_name: str):
    """获取工具详情"""
    registry = get_registry()
    tools = registry.discover(pattern=tool_name)

    if not tools:
        raise HTTPException(status_code=404, detail=f"Tool not found: {tool_name}")

    return tools[0]