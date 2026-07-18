"""Unified Chat API routes — /api/chat/ endpoint.

Phase A: Runs in parallel with /api/assistant/ and /api/qa/.
Phase B: Becomes the exclusive endpoint, old routes deprecated.
Phase C: Old routes removed.

Provides:
- POST /api/chat/message         — Unified SSE streaming (AG-UI + CUSTOM)
- POST /api/chat/tools/execute   — Direct tool execution (no LLM)
- GET  /api/chat/sessions        — List sessions
- POST /api/chat/sessions        — Create session
- DELETE /api/chat/sessions/{id} — Delete session
- GET  /api/chat/health          — Health check
"""

import json
import logging
from typing import Any, AsyncGenerator, Dict, List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field

from odap.biz.core.chat.engine.unified_chat_service import (
    UnifiedChatService,
    ChatRequest as UnifiedChatRequest,
)
from odap.infra.security.jwt_auth import get_current_user

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/chat", tags=["chat"])
_service = UnifiedChatService()


# ═══════════════════════════════════════════════════════════════════
# Request / Response models
# ═══════════════════════════════════════════════════════════════════

class ChatMessageRequest(BaseModel):
    """Unified chat message request."""
    message: str = Field(..., min_length=1, max_length=4000,
                         description="用户自然语言消息")
    session_id: Optional[str] = Field(None, description="会话ID（多轮对话）")
    ontology_id: Optional[str] = Field(None, description="当前本体ID")
    workspace_id: str = Field("default", description="工作空间ID")
    persona: str = Field("assistant", description="对话角色: assistant|qa|ontology-designer")
    context: Dict[str, Any] = Field(default_factory=dict, description="额外上下文")
    # QA-engine specific
    scenario_id: Optional[str] = Field(None, description="场景ID")
    agent_id: Optional[str] = Field(None, description="Agent ID")


class ToolExecuteRequest(BaseModel):
    """Direct tool execution request (no LLM decision-making)."""
    tool_name: str = Field(..., description="工具名称")
    parameters: Dict[str, Any] = Field(..., description="工具参数")


class SessionCreateRequest(BaseModel):
    """Create a new chat session."""
    workspace_id: str = Field("default")
    persona: str = Field("assistant")


class SessionResponse(BaseModel):
    """Session info response."""
    session_id: str
    created_at: str
    updated_at: str
    workspace_id: str
    persona: str
    message_count: int = 0


# ═══════════════════════════════════════════════════════════════════
# Helpers
# ═══════════════════════════════════════════════════════════════════

def _user_id(user) -> str:
    return user.get("sub", "anonymous") if isinstance(user, dict) else "anonymous"


# ═══════════════════════════════════════════════════════════════════
# Routes
# ═══════════════════════════════════════════════════════════════════

@router.post("/message")
async def chat_message(
    request: ChatMessageRequest,
    req: Request,
    user=Depends(get_current_user),
):
    """统一流式对话接口 (SSE, AG-UI + CUSTOM 协议).

    请求体:
    {
        "message": "请帮我分析本体的完整性",
        "ontology_id": "ont-xxx",          // 可选
        "session_id": "sess-xxx",          // 可选, 多轮对话
        "persona": "qa"                    // assistant|qa|ontology-designer
    }

    返回 SSE 事件流 (AG-UI 协议):
    - RUN_STARTED / RUN_FINISHED
    - TEXT_MESSAGE_START / TEXT_MESSAGE_CONTENT / TEXT_MESSAGE_END
    - TOOL_CALL_START / TOOL_CALL_END
    - CUSTOM: { custom_type: THINKING|SOURCES|CHART|TEMPORAL|REPORT|ONTOLOGY_CHANGED }

    单一执行路径:
    OpenHarness QueryEngine → Agent Loop → 17 tools → AG-UI SSE
    （无降级到 ChatService/QAEngineV2）
    """
    uid = _user_id(user)
    unified_req = UnifiedChatRequest(
        message=request.message,
        session_id=request.session_id,
        ontology_id=request.ontology_id,
        workspace_id=request.workspace_id,
        user_id=uid,
        context=request.context,
        persona=request.persona,
        scenario_id=request.scenario_id,
        agent_id=request.agent_id,
    )

    async def event_generator() -> AsyncGenerator[str, None]:
        try:
            async for event in _service.chat(unified_req):
                yield f"data: {json.dumps(event, ensure_ascii=False)}\n\n"
            yield "data: [DONE]\n\n"
        except HTTPException:
            raise
        except Exception as exc:
            logger.exception("Unified chat SSE error")
            yield f"data: {json.dumps({'type': 'ERROR', 'message': str(exc)}, ensure_ascii=False)}\n\n"

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )


@router.post("/tools/execute")
async def execute_tool(request: ToolExecuteRequest, user=Depends(get_current_user)):
    """直接执行工具（不经过 LLM）.

    可用工具:
    - list_entities, search_entities, query_relations, query_temporal
    - get_ontology_context, suggest_properties, suggest_relations, check_completeness
    - add_property, update_property, remove_property
    - create_object_type, delete_object_type, create_link_type, delete_link_type
    - add_properties (批量)
    """
    from odap.biz.core.chat.tools import TOOL_REGISTRY

    if request.tool_name not in TOOL_REGISTRY:
        raise HTTPException(status_code=404, detail=f"未知工具: {request.tool_name}")

    result = await _service.execute_tool(request.tool_name, request.parameters)
    if result.get("status") == "error":
        raise HTTPException(status_code=400, detail=result.get("message", "工具执行失败"))
    return result


@router.get("/health")
async def health():
    """统一对话服务健康检查 — 含韧性状态（熔断器、依赖健康、指标）。"""
    return _service.health()


# ═══════════════════════════════════════════════════════════════════
# Session management
# ═══════════════════════════════════════════════════════════════════

@router.get("/sessions", response_model=List[SessionResponse])
async def list_sessions(
    workspace_id: str = Query("default"),
    user=Depends(get_current_user),
):
    """列出当前用户的会话列表."""
    try:
        from odap.biz.data.qa.qa_engine import QAEngineV2
        engine = QAEngineV2()
        sessions = []
        for sid, s in engine.dialog_manager._sessions.items():
            sessions.append(SessionResponse(
                session_id=s.session_id,
                created_at=s.created_at,
                updated_at=s.updated_at,
                workspace_id=s.workspace_id or "default",
                persona="assistant",
                message_count=len(s.messages),
            ))
        return sessions
    except Exception as e:
        logger.warning("Failed to list sessions: %s", e)
        return []


@router.post("/sessions", response_model=SessionResponse)
async def create_session(
    request: SessionCreateRequest,
    user=Depends(get_current_user),
):
    """创建新会话."""
    try:
        from odap.biz.data.qa.qa_engine import QAEngineV2
        engine = QAEngineV2()
        uid = _user_id(user)
        session = engine.dialog_manager.create_session(
            user_id=uid,
            workspace_id=request.workspace_id,
        )
        return SessionResponse(
            session_id=session.session_id,
            created_at=session.created_at,
            updated_at=session.updated_at,
            workspace_id=session.workspace_id or request.workspace_id,
            persona=request.persona,
            message_count=0,
        )
    except Exception as e:
        logger.exception("Failed to create session")
        raise HTTPException(status_code=500, detail=str(e))


@router.delete("/sessions/{session_id}")
async def delete_session(session_id: str, user=Depends(get_current_user)):
    """删除会话."""
    try:
        from odap.biz.data.qa.qa_engine import QAEngineV2
        engine = QAEngineV2()
        with engine.dialog_manager._lock:
            if session_id in engine.dialog_manager._sessions:
                del engine.dialog_manager._sessions[session_id]
                return {"status": "deleted", "session_id": session_id}
            raise HTTPException(status_code=404, detail="会话不存在")
    except HTTPException:
        raise
    except Exception as e:
        logger.exception("Failed to delete session")
        raise HTTPException(status_code=500, detail=str(e))
