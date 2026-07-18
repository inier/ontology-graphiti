"""统一对话模块 — Unified Chat Service.

将原有的 ChatService (core/assistant/) 和 QAEngineV2 (data/qa/) 合并为
单一 UnifiedChatService，提供统一的对话端点、工具执行、RAG 检索和内容渲染。

模块结构:
- api/           统一 API 路由 (SSE 流式、工具执行、会话管理)
- engine/        统一对话引擎 (UnifiedChatService + SessionManager)
- tools/         工具注册表 (16 BaseTool，从 assitant/plugins/ 迁移)
- retrieval/     检索引擎 (BM25 + Vector + Graph，从 data/qa/retrieval/ 迁移)
- renderers/     内容渲染器 (chart / temporal / report / thinking)
- ontology_assistant/  本体辅助设计 (类型推断、约束建议、完整性检查)
"""

from odap.biz.core.chat.engine.unified_chat_service import UnifiedChatService

__all__ = ["UnifiedChatService"]
