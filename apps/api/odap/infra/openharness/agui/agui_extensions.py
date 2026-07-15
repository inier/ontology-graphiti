"""StreamEvent 派生扩展（OpenHarness 之上扩展，不修改核心）。

v2.0 架构关键不变量：
- ❌ 0 修改 `openharness/engine/stream_events.py`
- ✅ 派生 7 个新 dataclass，复用现有 `StreamEvent` 联合类型
- 这些类型与 agui_models.Pydantic 模型一一对应（dataclass 供 transport 层内部使用，
  Pydantic 供 wire 序列化使用）

OpenHarness 原生 7 类（惰性导入，避免环境无 anthropic SDK 时失败）：
    AssistantTextDelta, AssistantTurnComplete, ToolExecutionStarted,
    ToolExecutionCompleted, ErrorEvent, StatusEvent, CompactProgressEvent

AG-UI 协议需要但 OpenHarness 没有的（在这里派生）：
    RunStartedEvent, RunFinishedEvent, StepFinishedEvent,
    TextMessageStartEvent, TextMessageEndEvent,
    MessagesSnapshotEvent, StateSnapshotEvent
"""

from __future__ import annotations

import json
import uuid
from dataclasses import dataclass, field
from typing import Any, TYPE_CHECKING

if TYPE_CHECKING:
    # 仅类型检查时导入 OpenHarness 内部 dataclass
    from openharness.engine.stream_events import (
        AssistantTextDelta,
        AssistantTurnComplete,
        CompactProgressEvent,
        ErrorEvent,
        StatusEvent,
        ToolExecutionCompleted,
        ToolExecutionStarted,
    )


# === Run 生命周期事件 ===

@dataclass(frozen=True)
class RunStartedEvent:
    """AG-UI RUN_STARTED — run 生命周期首事件。"""

    thread_id: str
    run_id: str
    parent_run_id: str | None = None
    input: dict[str, Any] | None = None


@dataclass(frozen=True)
class RunFinishedEvent:
    """AG-UI RUN_FINISHED — run 生命周期终事件。

    outcome 字段：
    - "success" — 正常完成
    - {"type": "interrupt", "interrupts": [...]} — HITL 中断
    - {"type": "error", "error": "..."} — 异常退出
    """

    thread_id: str
    run_id: str
    outcome: str | dict[str, Any] = "success"
    result: dict[str, Any] | None = None


# === Step 事件 ===

@dataclass(frozen=True)
class StepFinishedEvent:
    """AG-UI STEP_FINISHED — 步骤结束。"""

    step_name: str


# === 文本消息边界事件 ===

@dataclass(frozen=True)
class TextMessageStartEvent:
    """AG-UI TEXT_MESSAGE_START — 文本消息开始。"""

    message_id: str
    role: str = "assistant"


@dataclass(frozen=True)
class TextMessageEndEvent:
    """AG-UI TEXT_MESSAGE_END — 文本消息结束。"""

    message_id: str


# === 状态快照事件 ===

@dataclass(frozen=True)
class MessagesSnapshotEvent:
    """AG-UI MESSAGES_SNAPSHOT — 完整消息历史快照。"""

    messages: list[dict[str, Any]] = field(default_factory=list)


@dataclass(frozen=True)
class StateSnapshotEvent:
    """AG-UI STATE_SNAPSHOT — 完整状态快照。"""

    snapshot: dict[str, Any] = field(default_factory=dict)


# === 工具调用 ID 稳定生成（被 transport 引用） ===

def make_tool_call_id(tool_name: str, tool_input: dict[str, Any]) -> str:
    """生成稳定的 tool_call_id（相同 (tool_name, tool_input) → 相同 ID）。"""
    canonical = json.dumps(tool_input, sort_keys=True, default=str)
    return f"tc-{tool_name}-{uuid.uuid5(uuid.NAMESPACE_OID, canonical).hex[:12]}"


def make_message_id(seed: str) -> str:
    """生成稳定的 message_id。"""
    return f"msg-{uuid.uuid5(uuid.NAMESPACE_OID, seed).hex[:12]}"


def make_interrupt_id() -> str:
    """生成 Interrupt ID（AG-UI 协议：RunFinished.interrupts[].id）。"""
    return f"int-{uuid.uuid4().hex[:12]}"


__all__ = [
    "RunStartedEvent",
    "RunFinishedEvent",
    "StepFinishedEvent",
    "TextMessageStartEvent",
    "TextMessageEndEvent",
    "MessagesSnapshotEvent",
    "StateSnapshotEvent",
    "make_tool_call_id",
    "make_message_id",
    "make_interrupt_id",
]


# === 自我验证：检查原文件未被修改（惰性，只在需要时调用） ===

def verify_openharness_unchanged() -> bool:
    """检查 OpenHarness StreamEvent 联合仍包含 7 类原生事件。

    可以在 import 时调用一次以验证不变量。
    返回 True = 完整, False = 缺失某些类型。
    """
    try:
        from openharness.engine.stream_events import StreamEvent
    except ImportError:
        # OpenHarness 不可用（如环境未安装 anthropic），跳过验证
        return False

    args = getattr(StreamEvent, "__args__", ())
    expected = {
        "AssistantTextDelta",
        "AssistantTurnComplete",
        "ToolExecutionStarted",
        "ToolExecutionCompleted",
        "ErrorEvent",
        "StatusEvent",
        "CompactProgressEvent",
    }
    actual = {getattr(t, "__name__", str(t)) for t in args}
    missing = expected - actual
    if missing:
        raise ImportError(
            f"OpenHarness StreamEvent missing expected types: {missing}. "
            "This may indicate openharness/engine/stream_events.py was modified. "
            "Architecture invariant: do not modify OpenHarness core."
        )
    return True
