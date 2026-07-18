"""Chat engine package — UnifiedChatService + Resilience + SwarmManager."""

from odap.biz.core.chat.engine.unified_chat_service import (
    UnifiedChatService,
    ChatRequest,
    verify_chat_service,
)
from odap.biz.core.chat.engine.resilience_manager import (
    ChatResilienceManager,
    get_chat_resilience,
    StartupHealthGate,
    ToolExecutionResilience,
    RetryPolicy,
)
from odap.biz.core.chat.engine.swarm_manager import (
    SwarmManager,
    get_swarm_manager,
    COMMANDER_PROMPT,
    INTELLIGENCE_PROMPT,
    OPERATIONS_PROMPT,
)

__all__ = [
    "UnifiedChatService",
    "ChatRequest",
    "verify_chat_service",
    "ChatResilienceManager",
    "get_chat_resilience",
    "StartupHealthGate",
    "ToolExecutionResilience",
    "RetryPolicy",
    "SwarmManager",
    "get_swarm_manager",
    "COMMANDER_PROMPT",
    "INTELLIGENCE_PROMPT",
    "OPERATIONS_PROMPT",
]
