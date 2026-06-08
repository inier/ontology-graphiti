"""Pydantic models for AG-UI protocol.

Reference: https://docs.ag-ui.com/concepts/events (AG-UI v0.x spec)

This module defines the wire-format models for the AG-UI protocol used by ODAP.
All field names follow the AG-UI spec (camelCase in JSON, snake_case in Python).
These models are pure data containers — no business logic.

Architecture invariant (v2.0 plan): 0 modifications to OpenHarness core.
The StreamEvent union defined in openharness.engine.stream_events is consumed
by the transport layer (agui_transport.py) and converted to these AG-UI events.
"""

from __future__ import annotations

from datetime import datetime
from enum import Enum
from typing import Any, Literal, Union

from pydantic import BaseModel, ConfigDict, Field


# === AG-UI 事件类型枚举（str + Enum 双继承，AGENTS.md 规则 4）===

class AGUIEventType(str, Enum):
    """AG-UI 17 类事件类型枚举。"""

    RUN_STARTED = "RUN_STARTED"
    RUN_FINISHED = "RUN_FINISHED"
    RUN_ERROR = "RUN_ERROR"
    STEP_STARTED = "STEP_STARTED"
    STEP_FINISHED = "STEP_FINISHED"
    TEXT_MESSAGE_START = "TEXT_MESSAGE_START"
    TEXT_MESSAGE_CONTENT = "TEXT_MESSAGE_CONTENT"
    TEXT_MESSAGE_END = "TEXT_MESSAGE_END"
    TOOL_CALL_START = "TOOL_CALL_START"
    TOOL_CALL_ARGS = "TOOL_CALL_ARGS"
    TOOL_CALL_END = "TOOL_CALL_END"
    TOOL_CALL_CHUNK = "TOOL_CALL_CHUNK"
    TOOL_CALL_RESULT = "TOOL_CALL_RESULT"
    STATE_SNAPSHOT = "STATE_SNAPSHOT"
    STATE_DELTA = "STATE_DELTA"
    MESSAGES_SNAPSHOT = "MESSAGES_SNAPSHOT"
    ACTIVITY_SNAPSHOT = "ACTIVITY_SNAPSHOT"


# === 基础模型（启用 camelCase 序列化）===

class AGUIBaseModel(BaseModel):
    """所有 AG-UI 事件基类。

    配置：
    - populate_by_name=True: 字段名同时接受 snake_case 和 camelCase
    - alias_generator: 序列化时 snake_case → camelCase
    - extra=allow: 允许 AG-UI 未来扩展新字段
    """

    model_config = ConfigDict(
        populate_by_name=True,
        alias_generator=None,  # 显式定义字段名，避免歧义
        extra="allow",
        use_enum_values=False,
    )


# === Run 生命周期事件 ===

class RunStartedEvent(AGUIBaseModel):
    """AG-UI RUN_STARTED — run 生命周期首事件。"""

    type: Literal["RUN_STARTED"] = "RUN_STARTED"
    threadId: str
    runId: str
    parentRunId: str | None = None
    input: dict[str, Any] | None = None


class RunFinishedOutcome(BaseModel):
    """Run 结束状态。success / interrupt / error 三态。"""

    outcome_type: str  # 内部字段，序列化为 type
    interrupts: list["Interrupt"] | None = None
    result: dict[str, Any] | None = None
    error: str | None = None

    model_config = ConfigDict(populate_by_name=True, extra="allow")

    def to_json(self) -> dict[str, Any]:
        out: dict[str, Any] = {}
        if self.outcome_type:
            out["type"] = self.outcome_type
        if self.interrupts:
            out["interrupts"] = [i.model_dump(by_alias=True) for i in self.interrupts]
        if self.result:
            out["result"] = self.result
        if self.error:
            out["error"] = self.error
        return out


class RunFinishedEvent(AGUIBaseModel):
    """AG-UI RUN_FINISHED — run 生命周期终事件。"""

    type: Literal["RUN_FINISHED"] = "RUN_FINISHED"
    threadId: str
    runId: str
    outcome: dict[str, Any] | str  # 字符串 "success" 或 {type: "interrupt", interrupts: [...]}
    result: dict[str, Any] | None = None


class RunErrorEvent(AGUIBaseModel):
    """AG-UI RUN_ERROR — run 发生不可恢复错误。"""

    type: Literal["RUN_ERROR"] = "RUN_ERROR"
    message: str
    code: str | None = None


# === Step 事件 ===

class StepStartedEvent(AGUIBaseModel):
    """AG-UI STEP_STARTED — 步骤开始。"""

    type: Literal["STEP_STARTED"] = "STEP_STARTED"
    stepName: str


class StepFinishedEvent(AGUIBaseModel):
    """AG-UI STEP_FINISHED — 步骤结束。"""

    type: Literal["STEP_FINISHED"] = "STEP_FINISHED"
    stepName: str


# === 文本消息事件 ===

class TextMessageStartEvent(AGUIBaseModel):
    """AG-UI TEXT_MESSAGE_START — 文本消息开始。

    在第一帧 TextMessageContent 之前 emit。message_id 由 transport 维护。
    """

    type: Literal["TEXT_MESSAGE_START"] = "TEXT_MESSAGE_START"
    messageId: str
    role: Literal["assistant", "user", "system", "tool"] = "assistant"


class TextMessageContentEvent(AGUIBaseModel):
    """AG-UI TEXT_MESSAGE_CONTENT — 增量文本。"""

    type: Literal["TEXT_MESSAGE_CONTENT"] = "TEXT_MESSAGE_CONTENT"
    messageId: str
    delta: str


class TextMessageEndEvent(AGUIBaseModel):
    """AG-UI TEXT_MESSAGE_END — 文本消息结束。"""

    type: Literal["TEXT_MESSAGE_END"] = "TEXT_MESSAGE_END"
    messageId: str


# === 工具调用事件 ===

class ToolCallStartEvent(AGUIBaseModel):
    """AG-UI TOOL_CALL_START — 工具调用开始。"""

    type: Literal["TOOL_CALL_START"] = "TOOL_CALL_START"
    toolCallId: str
    toolCallName: str
    parentMessageId: str | None = None


class ToolCallArgsEvent(AGUIBaseModel):
    """AG-UI TOOL_CALL_ARGS — 工具参数（可流式）。"""

    type: Literal["TOOL_CALL_ARGS"] = "TOOL_CALL_ARGS"
    toolCallId: str
    delta: str  # JSON 字符串


class ToolCallEndEvent(AGUIBaseModel):
    """AG-UI TOOL_CALL_END — 工具调用结束标记。"""

    type: Literal["TOOL_CALL_END"] = "TOOL_CALL_END"
    toolCallId: str


class ToolCallChunkEvent(AGUIBaseModel):
    """AG-UI TOOL_CALL_CHUNK — 工具流式输出（增量结果）。"""

    type: Literal["TOOL_CALL_CHUNK"] = "TOOL_CALL_CHUNK"
    toolCallId: str
    delta: str


class ToolCallResultEvent(AGUIBaseModel):
    """AG-UI TOOL_CALL_RESULT — 工具调用结果（完成时一次性 emit）。"""

    type: Literal["TOOL_CALL_RESULT"] = "TOOL_CALL_RESULT"
    messageId: str
    toolCallId: str
    content: str
    role: Literal["tool"] = "tool"


# === 状态事件 ===

class StateSnapshotEvent(AGUIBaseModel):
    """AG-UI STATE_SNAPSHOT — 完整状态快照。"""

    type: Literal["STATE_SNAPSHOT"] = "STATE_SNAPSHOT"
    snapshot: dict[str, Any] = Field(default_factory=dict)


class StateDeltaOp(BaseModel):
    """JSON Patch 风格的状态增量操作。"""

    op: Literal["add", "remove", "replace", "move", "copy", "test"]
    path: str
    value: Any | None = None
    from_: str | None = Field(default=None, alias="from")

    model_config = ConfigDict(populate_by_name=True, extra="allow")


class StateDeltaEvent(AGUIBaseModel):
    """AG-UI STATE_DELTA — 状态增量（JSON Patch）。"""

    type: Literal["STATE_DELTA"] = "STATE_DELTA"
    delta: list[StateDeltaOp] = Field(default_factory=list)


# === 消息快照事件 ===

class Message(BaseModel):
    """AG-UI Message — 对话消息。"""

    id: str
    role: Literal["user", "assistant", "system", "tool"]
    content: str | None = None
    name: str | None = None
    toolCallId: str | None = None
    toolCalls: list[dict[str, Any]] | None = None
    createdAt: datetime | None = None

    model_config = ConfigDict(populate_by_name=True, extra="allow")


class MessagesSnapshotEvent(AGUIBaseModel):
    """AG-UI MESSAGES_SNAPSHOT — 完整消息历史快照。"""

    type: Literal["MESSAGES_SNAPSHOT"] = "MESSAGES_SNAPSHOT"
    messages: list[Message] = Field(default_factory=list)


# === 活动快照事件（用于子 agent/工具状态） ===

class ActivitySnapshotEvent(AGUIBaseModel):
    """AG-UI ACTIVITY_SNAPSHOT — 活动快照。"""

    type: Literal["ACTIVITY_SNAPSHOT"] = "ACTIVITY_SNAPSHOT"
    activity: list[dict[str, Any]] = Field(default_factory=list)


# === AG-UI 事件联合（用于 type= 字段） ===

AGUIEvent = Union[
    RunStartedEvent,
    RunFinishedEvent,
    RunErrorEvent,
    StepStartedEvent,
    StepFinishedEvent,
    TextMessageStartEvent,
    TextMessageContentEvent,
    TextMessageEndEvent,
    ToolCallStartEvent,
    ToolCallArgsEvent,
    ToolCallEndEvent,
    ToolCallChunkEvent,
    ToolCallResultEvent,
    StateSnapshotEvent,
    StateDeltaEvent,
    MessagesSnapshotEvent,
    ActivitySnapshotEvent,
]


# === 请求/响应模型 ===

class InterruptReason(str, Enum):
    """AG-UI Interrupt 触发原因。"""

    CONFIRMATION = "confirmation"  # ask_user_question
    INPUT_REQUIRED = "input_required"  # ask_user_input
    TOOL_CALL = "tool_call"  # permission_prompt（危险工具拦截）
    CANCELLATION = "cancellation"  # 用户主动取消


class InterruptStatus(str, Enum):
    """Interrupt 响应状态。"""

    RESOLVED = "resolved"  # 用户已回答
    CANCELLED = "cancelled"  # 用户取消


class Interrupt(AGUIBaseModel):
    """AG-UI Interrupt — run 中断的恢复点。

    AG-UI 规范要求 RunFinished.outcome.interrupts[] 携带此结构。
    客户端发新 run 时通过 RunAgentInput.resume[] 携带响应。
    """

    id: str
    reason: InterruptReason
    message: str  # 人类可读描述
    responseSchema: dict[str, Any] | None = None  # 响应 JSON Schema
    toolCallId: str | None = None  # reason=tool_call 时携带
    metadata: dict[str, Any] = Field(default_factory=dict)


class ResumeEntry(AGUIBaseModel):
    """AG-UI Resume Entry — 客户端对 interrupt 的响应。"""

    interruptId: str
    status: InterruptStatus = InterruptStatus.RESOLVED
    response: dict[str, Any] = Field(default_factory=dict)


class Tool(BaseModel):
    """AG-UI Tool — 客户端可调用的前端工具声明。"""

    name: str
    description: str
    parameters: dict[str, Any] = Field(default_factory=dict)

    model_config = ConfigDict(populate_by_name=True, extra="allow")


class Context(BaseModel):
    """AG-UI Context — 客户端上下文（与消息一起提交）。"""

    description: str | None = None
    value: Any | None = None

    model_config = ConfigDict(populate_by_name=True, extra="allow")


class RunAgentInput(AGUIBaseModel):
    """AG-UI RunAgentInput — 客户端发起的 run 请求。

    这是 agui_handler 端点 POST /api/ag-ui/run 的请求体。
    """

    threadId: str
    runId: str
    parentRunId: str | None = None
    messages: list[Message] = Field(default_factory=list)
    tools: list[Tool] = Field(default_factory=list)
    context: list[Context] = Field(default_factory=list)
    state: dict[str, Any] = Field(default_factory=dict)
    resume: list[ResumeEntry] = Field(default_factory=list)
    forwardedProps: dict[str, Any] | None = None
    # ODAP 扩展字段
    workspaceId: str | None = None
    userId: str | None = None
    model: str | None = None


# === 卡片元数据（Generative UI 注册表使用） ===

class CardType(str, Enum):
    """ODAP 7 类内置卡片类型。"""

    CHART = "chart"  # ECharts 图表
    GRAPH = "graph"  # G6 图谱
    TEMPORAL = "temporal"  # 时间线
    REPORT_LINK = "report_link"  # 报告链接
    ACTION = "action"  # 行动按钮
    CONFIRM = "confirm"  # HITL 确认
    INPUT = "input"  # HITL 输入


class CardMetadata(AGUIBaseModel):
    """Generative UI 卡片元数据。"""

    card_type: CardType
    card_props: dict[str, Any] = Field(default_factory=dict)
    # 原始 tool_call 关联
    toolCallId: str | None = None
    toolName: str | None = None


# === 导出 ===

__all__ = [
    # 事件类型
    "AGUIEventType",
    "AGUIBaseModel",
    # 17 类事件
    "RunStartedEvent",
    "RunFinishedEvent",
    "RunErrorEvent",
    "StepStartedEvent",
    "StepFinishedEvent",
    "TextMessageStartEvent",
    "TextMessageContentEvent",
    "TextMessageEndEvent",
    "ToolCallStartEvent",
    "ToolCallArgsEvent",
    "ToolCallEndEvent",
    "ToolCallChunkEvent",
    "ToolCallResultEvent",
    "StateSnapshotEvent",
    "StateDeltaOp",
    "StateDeltaEvent",
    "Message",
    "MessagesSnapshotEvent",
    "ActivitySnapshotEvent",
    "AGUIEvent",
    # 请求/响应
    "InterruptReason",
    "InterruptStatus",
    "Interrupt",
    "ResumeEntry",
    "Tool",
    "Context",
    "RunAgentInput",
    "RunFinishedOutcome",
    # 卡片
    "CardType",
    "CardMetadata",
]
