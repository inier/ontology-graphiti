"""
L3 Application Chat — 统一 AI 助手 (Phase 2 桥接, ADR-068).

合并三套 AI 助手为单一入口:
  - ontology/assistant/   (T063, AG-UI SSE 协议)
  - core/assistant/       (插件式, tool-call 模式)
  - core/chat/            (UnifiedChatService, ADR-069/070)

当前以薄壳重新导出方式桥接，保持旧路由不变。
Phase 3 会将实现迁移到此位置。

子模块:
  - engine/      统一对话引擎
  - tools/       本体编辑工具 (design_tools / write_tools / query_tools)
  - retrieval/   RAG 检索引擎 (vector / BM25 / graph)
  - renderers/   内容渲染器 (chart / temporal / report / thinking)
"""

from odap.biz.core.assistant.services.chat_service import ChatService
from odap.biz.core.chat.engine.unified_chat_service import UnifiedChatService

# ontology/assistant/ 的 AG-UI 处理器
try:
    from odap.biz.core.ontology.assistant.services.assistant_service import (
        OntologyAssistantService,
    )
except ImportError:
    OntologyAssistantService = None

__all__ = [
    "ChatService",
    "UnifiedChatService",
    "OntologyAssistantService",
]
