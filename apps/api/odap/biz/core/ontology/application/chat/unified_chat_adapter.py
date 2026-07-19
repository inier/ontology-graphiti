"""AI助手统一桥接器。

将三套 AI 助手 (UnifiedChatService / ChatService / OntologyAssistant)
统一到一个入口，使用 UnifiedRetrieveEngine 作为检索后端。

ADR-069/070: 统一AI助手架构。
"""

from __future__ import annotations

import logging
import uuid
from typing import Any, Dict, Optional

logger = logging.getLogger(__name__)


class UnifiedChatAdapter:
    """AI助手统一适配器。

    将所有对话请求路由到 UnifiedChatService，使用 UnifiedRetrieveEngine 检索。
    """

    _instance: Optional["UnifiedChatAdapter"] = None

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._initialized = False
        return cls._instance

    def __init__(self):
        if self._initialized:
            return
        self._initialized = True

    async def chat(
        self,
        message: str,
        session_id: Optional[str] = None,
        ontology_id: Optional[str] = None,
        workspace_id: str = "default",
        persona: str = "assistant",
        use_reasoning: bool = True,
        max_retries: int = 2,
    ) -> Any:
        """统一对话入口（带重试和优雅降级）。

        Args:
            message: 用户消息
            session_id: 会话ID
            ontology_id: 本体ID
            workspace_id: 工作空间ID
            persona: 角色 (assistant/qa/ontology-designer)
            use_reasoning: 是否使用检索增强
            max_retries: 最大重试次数
        """
        import asyncio

        # 1. 检索增强（带超时保护）
        retrieval_context = ""
        if use_reasoning:
            try:
                retrieval_context = await asyncio.wait_for(
                    self._build_retrieval_context(message, workspace_id, ontology_id),
                    timeout=5.0,
                )
            except asyncio.TimeoutError:
                logger.warning("Retrieval context build timed out after 5s")
            except Exception as e:
                logger.debug("Retrieval enhancement skipped: %s", e)

        # 2. 路由到 UnifiedChatService（带重试）
        last_error = None
        for attempt in range(max_retries + 1):
            try:
                from odap.biz.core.chat.engine.unified_chat_service import UnifiedChatService
                chat_service = UnifiedChatService()

                input_message = retrieval_context + "\n\n" + message if retrieval_context else message

                async for event in chat_service.chat(request={
                    "message": input_message,
                    "session_id": session_id,
                    "ontology_id": ontology_id,
                    "workspace_id": workspace_id,
                    "persona": persona,
                }):
                    yield event
                return  # 成功，退出重试循环

            except ImportError:
                logger.warning("UnifiedChatService not available on attempt %d", attempt + 1)
                last_error = "UnifiedChatService unavailable"
                if attempt < max_retries:
                    await asyncio.sleep(0.5)
            except Exception as e:
                logger.error("Chat error on attempt %d: %s", attempt + 1, e)
                last_error = str(e)
                if attempt < max_retries:
                    await asyncio.sleep(1.0 * (attempt + 1))

        # 3. 优雅降级
        error_msg = last_error or "Unknown error"
        yield {"type": "TEXT_MESSAGE_START", "message_id": f"error-{uuid.uuid4().hex[:8]}"}
        yield {"type": "TEXT_MESSAGE_CONTENT", "message_id": f"error-{uuid.uuid4().hex[:8]}", "delta": f"抱歉，对话服务暂时不可用 ({error_msg[:100]})。收到你的消息: {message[:200]}"}
        yield {"type": "TEXT_MESSAGE_END", "message_id": f"error-{uuid.uuid4().hex[:8]}"}
        yield {"type": "RUN_FINISHED"}

    async def _build_retrieval_context(self, message: str, workspace_id: str, ontology_id: str) -> str:
        """构建检索上下文（提取为独立方法，便于超时控制）"""
        from odap.biz.core.ontology.reasoning.services.unified_retrieve import (
            RetrieveRequest, get_retrieve_engine,
        )
        engine = get_retrieve_engine()
        result = await engine.retrieve(RetrieveRequest(
            query=message,
            workspace_id=workspace_id,
            ontology_id=ontology_id,
            include_provenance=True,
            top_k=5,
        ))
        return self._format_retrieval_context(result.items) if result.items else ""

    def _format_retrieval_context(self, items: list) -> str:
        """格式化检索结果作为上下文"""
        lines = ["[检索上下文]"]
        for item in items:
            name = item.get("name", "unknown")
            itype = item.get("type", "")
            source = ""
            if item.get("provenance"):
                prov = item["provenance"]
                if prov.get("source", {}).get("document_name"):
                    source = f" (来自: {prov['source']['document_name']})"
            lines.append(f"- [{itype}] {name}{source}")
        return "\n".join(lines)


def get_chat_adapter() -> UnifiedChatAdapter:
    return UnifiedChatAdapter()


__all__ = ["UnifiedChatAdapter", "get_chat_adapter"]
