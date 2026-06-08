"""AG-UI extensions package.

This package implements the v2.0 pure-extension architecture for AG-UI
integration with OpenHarness.

Architecture invariant (v2.0 plan §1.1):
- 0 modifications to openharness/src/openharness/**
- 0 new odap/biz/core/qa/** module
- 0 new SQLite table
- Reuses: ask_user_prompt + permission_prompt + HookExecutor + Memory

Module structure:
- agui_models: Pydantic models (AG-UI v0.x wire format)
- agui_extensions: StreamEvent 派生 dataclasses (OpenHarness 扩展)
- agui_transport: OpenHarness StreamEvent → AG-UI Event 字段映射
- agui_handler: FastAPI endpoint + QueryEngine 集成
"""

from __future__ import annotations

from odap.infra.openharness.agui.agui_models import (  # noqa: F401
    AGUIBaseModel,
    AGUIEvent,
    AGUIEventType,
    CardMetadata,
    CardType,
    Context,
    Interrupt,
    InterruptReason,
    InterruptStatus,
    Message,
    MessagesSnapshotEvent,
    ResumeEntry,
    RunAgentInput,
    RunErrorEvent,
    RunFinishedEvent,
    RunFinishedOutcome,
    RunStartedEvent,
    StateDeltaEvent,
    StateDeltaOp,
    StateSnapshotEvent,
    StepFinishedEvent,
    StepStartedEvent,
    TextMessageContentEvent,
    TextMessageEndEvent,
    TextMessageStartEvent,
    Tool,
    ToolCallArgsEvent,
    ToolCallChunkEvent,
    ToolCallEndEvent,
    ToolCallResultEvent,
    ToolCallStartEvent,
    ActivitySnapshotEvent,
)

__version__ = "2.0.0"
__all__ = [
    "__version__",
    "AGUIBaseModel",
    "AGUIEvent",
    "AGUIEventType",
    "CardMetadata",
    "CardType",
    "Context",
    "Interrupt",
    "InterruptReason",
    "InterruptStatus",
    "Message",
    "MessagesSnapshotEvent",
    "ResumeEntry",
    "RunAgentInput",
    "RunErrorEvent",
    "RunFinishedEvent",
    "RunFinishedOutcome",
    "RunStartedEvent",
    "StateDeltaEvent",
    "StateDeltaOp",
    "StateSnapshotEvent",
    "StepFinishedEvent",
    "StepStartedEvent",
    "TextMessageContentEvent",
    "TextMessageEndEvent",
    "TextMessageStartEvent",
    "Tool",
    "ToolCallArgsEvent",
    "ToolCallChunkEvent",
    "ToolCallEndEvent",
    "ToolCallResultEvent",
    "ToolCallStartEvent",
    "ActivitySnapshotEvent",
]
