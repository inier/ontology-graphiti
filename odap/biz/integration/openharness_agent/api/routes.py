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
import logging

from odap.infra.openharness.v2_adapter import (
    get_openharness_integration,
    initialize_openharness,
    run_agent,
)

logger = logging.getLogger(__name__)

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


class AgentInitRequest(BaseModel):
    config: Optional[Dict[str, Any]] = None
    user_role: Optional[str] = "intelligence_analyst"
    provider_config: Optional[Dict[str, Any]] = None


class AgentChatRequest(BaseModel):
    message: str
    session_id: Optional[str] = None
    workspace_id: Optional[str] = None
    role: Optional[str] = None


@router.post("/init")
async def init_agent_compat(request: AgentInitRequest):
    config = request.config or {}
    user_role = config.get("user_role", request.user_role) if isinstance(config, dict) else request.user_role
    provider_config = config.get("provider_config", request.provider_config) if isinstance(config, dict) else request.provider_config
    try:
        success = await initialize_openharness(
            user_role=user_role,
            provider_config=provider_config,
        )
        if success:
            integration = get_openharness_integration()
            status = integration.get_status()
            return {"success": True, "message": "Agent 初始化成功", "status": status}
        else:
            return {"success": False, "message": "Agent 初始化失败"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


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
async def chat_with_agent(request: AgentChatRequest):
    try:
        from odap.biz.platform.session_memory.session_store import SessionStore, Session
        from odap.biz.platform.session_memory.context_window import ChatMessage, MessageRole

        context = {}
        if request.session_id:
            context["session_id"] = request.session_id
        if request.workspace_id:
            context["workspace_id"] = request.workspace_id
        if request.role:
            context["role"] = request.role

        session = None
        store = None
        workspace_id = request.workspace_id or "default"

        if request.session_id:
            try:
                store = SessionStore()
                session = store.load_session(request.session_id)
                if session:
                    history = [
                        {"role": m.role.value, "content": m.content}
                        for m in session.messages
                    ]
                    if history:
                        context["chat_history"] = history
            except Exception as e:
                logger.warning(f"Failed to load session {request.session_id}: {e}")

        result = await run_agent(
            user_input=request.message,
            context=context if context else None,
        )

        response_data = {"response": {"error": "执行失败"}, "steps_count": 0}
        if isinstance(result, dict) and result.get("success"):
            steps = result.get("steps", [])
            if steps:
                last_step = steps[-1]
                response_data = {
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

        try:
            if store is None:
                store = SessionStore()
            if session is None:
                session = Session(
                    workspace_id=workspace_id,
                    title=request.message[:80] if request.message else "New Session",
                )
            session.messages.append(
                ChatMessage(role=MessageRole.USER, content=request.message)
            )
            assistant_content = ""
            resp = response_data.get("response", {})
            if isinstance(resp, dict):
                assistant_content = resp.get("output", resp.get("message", str(resp)))
            elif isinstance(resp, str):
                assistant_content = resp
            else:
                assistant_content = str(resp)
            session.messages.append(
                ChatMessage(role=MessageRole.ASSISTANT, content=assistant_content)
            )
            store.save_session(session)
            response_data["session_id"] = session.id
        except Exception as e:
            logger.warning(f"Failed to save session: {e}")

        return response_data
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/sessions")
async def list_agent_sessions(workspace_id: str = "default", limit: int = 20):
    try:
        from odap.biz.platform.session_memory.session_store import SessionStore
        store = SessionStore()
        sessions = store.list_sessions(workspace_id=workspace_id, limit=limit)
        return {"sessions": [s.model_dump() for s in sessions]}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.delete("/sessions/{session_id}")
async def delete_agent_session(session_id: str):
    try:
        from odap.biz.platform.session_memory.session_store import SessionStore
        store = SessionStore()
        deleted = store.delete_session(session_id)
        if not deleted:
            raise HTTPException(status_code=404, detail=f"Session {session_id} not found")
        return {"status": "ok", "session_id": session_id}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
