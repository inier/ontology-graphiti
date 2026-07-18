"""Unified AI Assistant API routes.

POST /api/assistant/chat  — SSE streaming chat endpoint (AG-UI protocol)
GET  /api/assistant/health — Health check

Architecture (Phase 2):
- 主路径：AGUI 桥接 → OpenHarness QueryEngine → AG-UI SSE 事件
- 降级路径：ChatService.chat() → 自定义 SSE 事件（OpenHarness 不可用时）
- 工具通过 ToolRegistry 调用（AI Assistant Plugin 的 16 个 BaseTool）
"""
import json
import logging
from typing import Any, AsyncGenerator, Dict, Optional

from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field

from odap.biz.core.assistant.services.chat_service import ChatService
from odap.infra.security.jwt_auth import get_current_user

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/assistant", tags=["assistant"])
_service = ChatService()


class ChatRequest(BaseModel):
    message: str = Field(..., min_length=1, max_length=2000,
                         description="用户自然语言消息")
    ontology_id: Optional[str] = Field(None, description="当前本体ID")
    workspace_id: Optional[str] = Field("default", description="工作空间ID")
    session_id: Optional[str] = Field(None, description="会话ID")
    context: Optional[Dict[str, Any]] = Field(None, description="额外上下文")


def _user_id(user) -> str:
    return user.get("sub", "anonymous") if isinstance(user, dict) else "anonymous"


def _is_agui_available() -> bool:
    """检查 AGUI 桥接路径是否可用（OpenHarness 已初始化）。"""
    try:
        from odap.infra.openharness.engine_adapter import OPENHARNESS_AVAILABLE
        return OPENHARNESS_AVAILABLE
    except ImportError:
        return False


@router.post("/chat")
async def chat(
    request: ChatRequest,
    req: Request,
    user=Depends(get_current_user),
):
    """统一AI助手对话接口 (SSE 流式响应)

    请求体:
    {
        "message": "有哪些实体？",
        "ontology_id": "ont-xxx",       // 可选: 当前本体ID
        "workspace_id": "default",       // 可选: 工作空间
        "session_id": "sess-xxx",        // 可选: 会话ID
        "context": {                      // 可选: 页面上下文
            "object_type": "User",
            "page": "ontology_designer"
        }
    }

    返回 SSE 事件流 (AG-UI 协议):
    - type: "RUN_STARTED" | "TEXT_MESSAGE_START" | "TEXT_MESSAGE_CONTENT"
           | "TEXT_MESSAGE_END" | "TOOL_CALL_START" | "TOOL_CALL_END"
           | "CUSTOM" | "RUN_FINISHED"

    架构路径:
    - 主路径: AGUI 桥接 → OpenHarness QueryEngine → AG-UI SSE
    - 降级路径: ChatService.chat() → 自定义 SSE (OpenHarness 不可用时)
    """
    uid = _user_id(user)

    # 主路径：AGUI 桥接（基于 OpenHarness QueryEngine）
    if _is_agui_available():
        try:
            from odap.infra.openharness.agui.web_channel import chat_via_agui

            return StreamingResponse(
                chat_via_agui(
                    request.message,
                    ontology_id=request.ontology_id,
                    workspace_id=request.workspace_id or "default",
                    session_id=request.session_id,
                    context=request.context,
                    user_id=uid,
                ),
                media_type="text/event-stream",
                headers={
                    "Cache-Control": "no-cache",
                    "Connection": "keep-alive",
                    "X-Accel-Buffering": "no",
                },
            )
        except HTTPException:
            # AGENTS.md 规则 3：HTTPException 必须透传，不能被降级吞掉
            raise
        except Exception as e:
            logger.warning("AGUI bridge failed, falling back to ChatService: %s", e)

    # 降级路径：ChatService（OpenHarness 不可用时）
    async def event_generator() -> AsyncGenerator[str, None]:
        try:
            async for event in _service.chat(
                message=request.message,
                ontology_id=request.ontology_id,
                workspace_id=request.workspace_id or "default",
                session_id=request.session_id,
                user_id=uid,
                context=request.context,
            ):
                yield f"data: {json.dumps(event, ensure_ascii=False)}\n\n"
            yield "data: [DONE]\n\n"
        except HTTPException:
            # AGENTS.md 规则 3：HTTPException 透传，不降级为 SSE ERROR 事件
            raise
        except Exception as e:
            logger.exception("Chat SSE error (fallback path)")
            yield f"data: {json.dumps({'type': 'ERROR', 'message': str(e)}, ensure_ascii=False)}\n\n"

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )


@router.get("/health")
async def health():
    """检查 AI 助手服务状态"""
    return {
        "status": "available",
        "llm_available": _service.llm is not None,
        "features": [
            "entity_query", "entity_search", "relation_query",
            "temporal_query", "ontology_context", "completeness_check",
            "property_suggestions", "relation_suggestions",
        ],
    }


class ToolExecuteRequest(BaseModel):
    """直接执行工具请求（不经过 LLM）"""
    tool_name: str = Field(..., description="工具名称")
    parameters: Dict[str, Any] = Field(..., description="工具参数")


@router.post("/tools/execute")
async def execute_tool_direct(request: ToolExecuteRequest, user=Depends(get_current_user)):
    """直接执行工具，不经过 LLM（用于前端快捷操作）
    
    可用工具:
    - suggest_properties: 建议属性
    - suggest_relations: 建议关系
    - get_ontology_context: 获取本体上下文
    - check_completeness: 检查完整性
    - list_entities: 列出实体
    - search_entities: 搜索实体
    - query_relations: 查询关系
    """
    from odap.biz.core.assistant.plugins.ai_assistant.registry import execute_tool_async, TOOL_REGISTRY
    
    if request.tool_name not in TOOL_REGISTRY:
        raise HTTPException(status_code=404, detail=f"工具不存在: {request.tool_name}")
    
    try:
        result = await execute_tool_async(request.tool_name, request.parameters)
        return {
            "status": "success",
            "tool_name": request.tool_name,
            "result": result,
        }
    except HTTPException:
        # AGENTS.md 规则 3：工具内部抛 HTTPException（如 404）必须透传，不能被 500 吞掉
        raise
    except Exception as e:
        logger.exception("Tool execution failed")
        raise HTTPException(status_code=500, detail=f"工具执行失败: {str(e)}")
