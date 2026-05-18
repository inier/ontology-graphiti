"""
OpenHarness Agent API 路由

提供完整的 Agent Loop API：
- /agent/run - 运行 Agent
- /agent/status - 获取状态
- /agent/tools - 列出工具
- /agent/history - 获取历史
"""

from fastapi import APIRouter, HTTPException
from typing import Dict, Any, List, Optional
from pydantic import BaseModel

from odap.infra.openharness.v2_adapter import (
    get_openharness_integration,
    initialize_openharness,
    run_agent,
)

router = APIRouter(prefix="/api/agent", tags=["openharness-agent"])


class AgentRunRequest(BaseModel):
    """Agent 运行请求"""
    input: str
    context: Optional[Dict[str, Any]] = None
    max_steps: Optional[int] = 50


class AgentConfigRequest(BaseModel):
    """Agent 配置请求"""
    user_role: str = "intelligence_analyst"
    provider_config: Optional[Dict[str, Any]] = None


@router.post("/initialize")
async def initialize_agent(config: AgentConfigRequest):
    """
    初始化 Agent
    
    Args:
        config: 配置信息
        
    Returns:
        初始化结果
    """
    try:
        success = await initialize_openharness(
            user_role=config.user_role,
            provider_config=config.provider_config,
        )
        
        if success:
            integration = get_openharness_integration()
            status = integration.get_status()
            return {
                "success": True,
                "message": "Agent 初始化成功",
                "status": status,
            }
        else:
            return {
                "success": False,
                "message": "Agent 初始化失败",
            }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/run")
async def run_agent_endpoint(request: AgentRunRequest):
    """
    运行 Agent
    
    Args:
        request: 运行请求
        
    Returns:
        运行结果
    """
    try:
        result = await run_agent(
            user_input=request.input,
            context=request.context,
        )
        
        return result
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/status")
async def get_agent_status():
    """
    获取 Agent 状态
    
    Returns:
        状态信息
    """
    try:
        integration = get_openharness_integration()
        return integration.get_status()
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/tools")
async def list_agent_tools():
    """
    列出所有可用工具
    
    Returns:
        工具列表
    """
    try:
        integration = get_openharness_integration()
        status = integration.get_status()
        return {
            "tools": status.get("tools", []),
            "count": status.get("tools_count", 0),
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/chat")
async def chat_with_agent(request: AgentRunRequest):
    """
    与 Agent 对话（简化接口，委托给 /run）
    """
    try:
        result = await run_agent_endpoint(request)

        if isinstance(result, dict) and result.get("success"):
            steps = result.get("steps", [])
            if steps:
                last_step = steps[-1]
                return {
                    "response": last_step.get("result", {}),
                    "steps_count": len(steps),
                    "thought_process": [
                        {
                            "step": step.get("step"),
                            "action": step.get("action", {}).get("tool_name"),
                            "thought": step.get("action", {}).get("thought"),
                        }
                        for step in steps
                    ],
                }

        return {
            "response": {"error": "执行失败"},
            "steps_count": 0,
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
