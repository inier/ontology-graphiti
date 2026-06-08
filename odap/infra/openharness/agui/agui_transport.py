"""AG-UI Transport Layer — OpenHarness StreamEvent → AG-UI Event 字段映射。

v2.0 架构：本模块是 emit 层（非翻译层），99% 是字段名映射。
OpenHarness StreamEvent 类型不可修改，由本模块 isinstance 分发到对应 AG-UI Event。

State machine（维护 text message 边界）：
- 第一帧 AssistantTextDelta → 自动注入 TextMessageStartEvent
- AssistantTurnComplete → 自动注入 TextMessageEndEvent
- ToolExecutionStarted → 自动展开为 3 件套（START/ARGS/END）
- ToolExecutionCompleted → 1 件 TOOL_CALL_RESULT
"""

from __future__ import annotations

import json
from typing import Any

from odap.infra.openharness.agui.agui_extensions import (
    MessagesSnapshotEvent,
    RunFinishedEvent,
    RunStartedEvent,
    StateSnapshotEvent,
    StepFinishedEvent,
    TextMessageEndEvent,
    TextMessageStartEvent,
    make_message_id,
    make_tool_call_id,
)


# === Transport state（per-run）===

class TransportState:
    """单次 run 的 transport 状态（text message 边界 + tool_call_id 跟踪）。

    一个 run 对应一个 TransportState 实例。在 agui_handler.run_agent() 中创建。
    """

    def __init__(self, thread_id: str, run_id: str, model: str = "") -> None:
        self.thread_id = thread_id
        self.run_id = run_id
        self.model = model
        # text message 状态
        self.current_message_id: str | None = None
        # tool_call 状态（去重）
        self.active_tool_calls: dict[str, str] = {}  # tool_name → tool_call_id


# === 主入口：OpenHarness StreamEvent → AG-UI Event ===

def to_agui_events(
    event: Any,
    state: TransportState,
) -> list[dict[str, Any]]:
    """把 OpenHarness StreamEvent（或派生）序列化为 AG-UI Event JSON dict 列表。

    Args:
        event: OpenHarness StreamEvent 或 agui_extensions 派生类
        state: TransportState 实例（per-run）

    Returns:
        AG-UI Event JSON dict 列表（一个 OpenHarness 事件可能产生 0~3 个 AG-UI 事件）。
        返回 [] 表示该事件被忽略（如 AssistantTurnComplete 在 Start 之后但 End 之前）。

    Notes:
        此函数**不调用** transport 自动注入逻辑（TextMessageStart/End）。
        调用方应使用 `wrap_with_state_machine` 包装以获得自动注入。
    """
    # === 派生类（7 个）— 严格 isinstance，避免与 OpenHarness 同名 dataclass 冲突 ===
    if isinstance(event, RunStartedEvent):
        return [_to_run_started(event)]
    if isinstance(event, RunFinishedEvent):
        return [_to_run_finished(event)]
    if isinstance(event, StepFinishedEvent):
        return [_to_step_finished(event)]
    if isinstance(event, TextMessageStartEvent):
        state.current_message_id = event.message_id
        return [_to_text_message_start(event)]
    if isinstance(event, TextMessageEndEvent):
        out = [_to_text_message_end(event)]
        if state.current_message_id == event.message_id:
            state.current_message_id = None
        return out
    if isinstance(event, MessagesSnapshotEvent):
        return [_to_messages_snapshot(event)]
    if isinstance(event, StateSnapshotEvent):
        return [_to_state_snapshot(event)]

    # === OpenHarness 原生 7 类 — Duck typing 字段检测 ===
    # 避免在缺 anthropic SDK 的环境无法 isinstance OpenHarness 类的限制
    # 检测顺序：tool > text > status > compact > error
    if hasattr(event, "tool_name") and hasattr(event, "tool_input") and not hasattr(event, "output"):
        return _handle_tool_execution_started(event, state)
    if hasattr(event, "tool_name") and hasattr(event, "output") and hasattr(event, "is_error"):
        return _handle_tool_execution_completed(event, state)
    if hasattr(event, "phase") and hasattr(event, "trigger") and hasattr(event, "attempt"):
        return _handle_compact_progress_event(event, state)
    if hasattr(event, "text"):
        return _handle_assistant_text_delta(event, state)
    if hasattr(event, "message") and hasattr(event, "usage") and hasattr(event, "message"):
        return _handle_assistant_turn_complete(event, state)
    if hasattr(event, "recoverable") and hasattr(event, "message"):
        return _handle_error_event(event, state)
    if hasattr(event, "message"):
        return _handle_status_event(event, state)

    return []  # 未知类型静默忽略


# === OpenHarness 7 类原生事件处理器（按 class name 路由） ===

def _handle_assistant_text_delta(event: Any, state: TransportState) -> list[dict[str, Any]]:
    """AssistantTextDelta(text) → TEXT_MESSAGE_CONTENT(+可选 Start 注入)。"""
    out: list[dict[str, Any]] = []

    # 第一帧 delta → 自动注入 TextMessageStart
    if state.current_message_id is None:
        # OpenHarness 没传 seed；用确定性 hash 稳定生成
        seed = f"{state.thread_id}-{state.run_id}-{id(state)}"
        message_id = make_message_id(seed)
        state.current_message_id = message_id
        out.append({
            "type": "TEXT_MESSAGE_START",
            "messageId": message_id,
            "role": "assistant",
        })

    out.append({
        "type": "TEXT_MESSAGE_CONTENT",
        "messageId": state.current_message_id,
        "delta": event.text,
    })
    return out


def _handle_assistant_turn_complete(event: Any, state: TransportState) -> list[dict[str, Any]]:
    """AssistantTurnComplete → TEXT_MESSAGE_END。"""
    if state.current_message_id is None:
        return []  # 没有正在进行的消息
    out = [{
        "type": "TEXT_MESSAGE_END",
        "messageId": state.current_message_id,
    }]
    state.current_message_id = None
    return out


def _handle_tool_execution_started(event: Any, state: TransportState) -> list[dict[str, Any]]:
    """ToolExecutionStarted → TOOL_CALL_START + ARGS + END 三件套。"""
    tool_name = event.tool_name
    tool_input = event.tool_input
    tool_call_id = make_tool_call_id(tool_name, tool_input)
    state.active_tool_calls[tool_name] = tool_call_id
    parent_msg = state.current_message_id
    return [
        {
            "type": "TOOL_CALL_START",
            "toolCallId": tool_call_id,
            "toolCallName": tool_name,
            **({"parentMessageId": parent_msg} if parent_msg else {}),
        },
        {
            "type": "TOOL_CALL_ARGS",
            "toolCallId": tool_call_id,
            "delta": json.dumps(tool_input, default=str),
        },
        {
            "type": "TOOL_CALL_END",
            "toolCallId": tool_call_id,
        },
    ]


def _handle_tool_execution_completed(event: Any, state: TransportState) -> list[dict[str, Any]]:
    """ToolExecutionCompleted → TOOL_CALL_RESULT。"""
    tool_call_id = state.active_tool_calls.get(event.tool_name) or make_tool_call_id(
        event.tool_name, {"_result": event.output}
    )
    return [{
        "type": "TOOL_CALL_RESULT",
        "messageId": state.current_message_id or "",
        "toolCallId": tool_call_id,
        "content": event.output,
        "role": "tool",
    }]


def _handle_error_event(event: Any, state: TransportState) -> list[dict[str, Any]]:
    """ErrorEvent → RUN_ERROR。"""
    out = [{
        "type": "RUN_ERROR",
        "message": event.message,
        "code": None,
    }]
    if not event.recoverable:
        out.append({
            "type": "RUN_FINISHED",
            "threadId": state.thread_id,
            "runId": state.run_id,
            "outcome": {"type": "error", "error": event.message},
        })
    return out


def _handle_status_event(event: Any, state: TransportState) -> list[dict[str, Any]]:
    """StatusEvent → STEP_STARTED（带一个隐含 STEP_FINISHED 标记）。"""
    return [{
        "type": "STEP_STARTED",
        "stepName": event.message,
    }]


def _handle_compact_progress_event(event: Any, state: TransportState) -> list[dict[str, Any]]:
    """CompactProgressEvent → STATE_DELTA（compact 进度）。"""
    return [{
        "type": "STATE_DELTA",
        "delta": [{
            "op": "replace",
            "path": "/compact",
            "value": {
                "phase": event.phase,
                "message": event.message,
                "attempt": event.attempt,
            },
        }],
    }]


_OPENHARNESS_HANDLERS = {
    "AssistantTextDelta": _handle_assistant_text_delta,
    "AssistantTurnComplete": _handle_assistant_turn_complete,
    "ToolExecutionStarted": _handle_tool_execution_started,
    "ToolExecutionCompleted": _handle_tool_execution_completed,
    "ErrorEvent": _handle_error_event,
    "StatusEvent": _handle_status_event,
    "CompactProgressEvent": _handle_compact_progress_event,
}


# === 派生类 → AG-UI 字段映射（最小封装）===

def _to_run_started(e: RunStartedEvent) -> dict[str, Any]:
    return {
        "type": "RUN_STARTED",
        "threadId": e.thread_id,
        "runId": e.run_id,
        "parentRunId": e.parent_run_id,
        "input": e.input,
    }


def _to_run_finished(e: RunFinishedEvent) -> dict[str, Any]:
    out: dict[str, Any] = {
        "type": "RUN_FINISHED",
        "threadId": e.thread_id,
        "runId": e.run_id,
        "outcome": e.outcome,
    }
    if e.result is not None:
        out["result"] = e.result
    return out


def _to_step_finished(e: StepFinishedEvent) -> dict[str, Any]:
    return {"type": "STEP_FINISHED", "stepName": e.step_name}


def _to_text_message_start(e: TextMessageStartEvent) -> dict[str, Any]:
    return {"type": "TEXT_MESSAGE_START", "messageId": e.message_id, "role": e.role}


def _to_text_message_end(e: TextMessageEndEvent) -> dict[str, Any]:
    return {"type": "TEXT_MESSAGE_END", "messageId": e.message_id}


def _to_messages_snapshot(e: MessagesSnapshotEvent) -> dict[str, Any]:
    return {"type": "MESSAGES_SNAPSHOT", "messages": e.messages}


def _to_state_snapshot(e: StateSnapshotEvent) -> dict[str, Any]:
    return {"type": "STATE_SNAPSHOT", "snapshot": e.snapshot}


# === JSON 编码辅助 ===

def encode_sse(event_dict: dict[str, Any]) -> str:
    """把 AG-UI Event dict 编码为 SSE data 字段。

    SSE 格式：`data: {json}\n\n`
    """
    return f"data: {json.dumps(event_dict, default=str, ensure_ascii=False)}\n\n"


__all__ = [
    "TransportState",
    "to_agui_events",
    "encode_sse",
]
