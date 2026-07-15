"""Unit tests for AG-UI transport layer.

Per AGENTS.md 规则 9: 新增模块必须测试。
Per plan v2.0 T016: 7 cases 覆盖 OpenHarness 7 类 StreamEvent → AG-UI Event 字段映射。

Test strategy:
- 不依赖真实的 OpenHarness 实例（环境可能无 anthropic SDK）
- 用 duck-typed mock dataclass 模拟 OpenHarness 7 类原生事件
- 验证 transport 输出的 AG-UI Event dict 符合协议规格
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

import pytest

from odap.infra.openharness.agui.agui_extensions import (
    MessagesSnapshotEvent,
    RunFinishedEvent,
    RunStartedEvent,
    StateSnapshotEvent,
    StepFinishedEvent,
    TextMessageEndEvent,
    TextMessageStartEvent,
    make_tool_call_id,
)
from odap.infra.openharness.agui.agui_transport import (
    TransportState,
    encode_sse,
    to_agui_events,
)


# === Mock OpenHarness 7 类原生事件（避免依赖 anthropic）===

@dataclass
class MockAssistantTextDelta:
    text: str


@dataclass
class MockAssistantTurnComplete:
    message: Any = None
    usage: Any = None


@dataclass
class MockToolExecutionStarted:
    tool_name: str
    tool_input: dict[str, Any] = field(default_factory=dict)


@dataclass
class MockToolExecutionCompleted:
    tool_name: str
    output: str
    is_error: bool = False


@dataclass
class MockErrorEvent:
    message: str
    recoverable: bool = True


@dataclass
class MockStatusEvent:
    message: str


@dataclass
class MockCompactProgressEvent:
    phase: str
    trigger: str
    message: str | None = None
    attempt: int | None = None


# === 派生事件类（agui_extensions）的 transport 验证 ===

class TestDerivedEvents:
    def test_run_started_to_wire(self):
        state = TransportState(thread_id="t1", run_id="r1")
        e = RunStartedEvent(thread_id="t1", run_id="r1", parent_run_id="r0",
                            input={"messages": [{"role": "user", "content": "hi"}]})
        out = to_agui_events(e, state)
        assert len(out) == 1
        assert out[0]["type"] == "RUN_STARTED"
        assert out[0]["threadId"] == "t1"
        assert out[0]["runId"] == "r1"
        assert out[0]["parentRunId"] == "r0"
        assert out[0]["input"]["messages"][0]["content"] == "hi"

    def test_run_finished_success(self):
        state = TransportState(thread_id="t1", run_id="r1")
        e = RunFinishedEvent(thread_id="t1", run_id="r1", outcome="success",
                              result={"usage": {"tokens": 100}})
        out = to_agui_events(e, state)
        assert len(out) == 1
        assert out[0]["type"] == "RUN_FINISHED"
        assert out[0]["outcome"] == "success"
        assert out[0]["result"]["usage"]["tokens"] == 100

    def test_run_finished_interrupt(self):
        state = TransportState(thread_id="t1", run_id="r1")
        e = RunFinishedEvent(thread_id="t1", run_id="r1", outcome={
            "type": "interrupt",
            "interrupts": [{"id": "int-1", "reason": "confirmation", "message": "?"}],
        })
        out = to_agui_events(e, state)
        assert out[0]["outcome"]["type"] == "interrupt"
        assert out[0]["outcome"]["interrupts"][0]["reason"] == "confirmation"

    def test_step_finished(self):
        state = TransportState(thread_id="t1", run_id="r1")
        e = StepFinishedEvent(step_name="query")
        out = to_agui_events(e, state)
        assert out[0] == {"type": "STEP_FINISHED", "stepName": "query"}

    def test_text_message_start(self):
        state = TransportState(thread_id="t1", run_id="r1")
        e = TextMessageStartEvent(message_id="m1", role="assistant")
        out = to_agui_events(e, state)
        assert out[0]["type"] == "TEXT_MESSAGE_START"
        assert out[0]["messageId"] == "m1"
        # state 应被更新
        assert state.current_message_id == "m1"

    def test_text_message_end(self):
        state = TransportState(thread_id="t1", run_id="r1")
        state.current_message_id = "m1"
        e = TextMessageEndEvent(message_id="m1")
        out = to_agui_events(e, state)
        assert out[0] == {"type": "TEXT_MESSAGE_END", "messageId": "m1"}
        # 状态机应清空
        assert state.current_message_id is None

    def test_messages_snapshot(self):
        state = TransportState(thread_id="t1", run_id="r1")
        e = MessagesSnapshotEvent(messages=[
            {"id": "m1", "role": "user", "content": "hi"},
            {"id": "m2", "role": "assistant", "content": "hello"},
        ])
        out = to_agui_events(e, state)
        assert out[0]["type"] == "MESSAGES_SNAPSHOT"
        assert len(out[0]["messages"]) == 2

    def test_state_snapshot(self):
        state = TransportState(thread_id="t1", run_id="r1")
        e = StateSnapshotEvent(snapshot={
            "memory": {"facts": ["f1"]},
            "active_skills": ["ask_user_question"],
        })
        out = to_agui_events(e, state)
        assert out[0]["type"] == "STATE_SNAPSHOT"
        assert out[0]["snapshot"]["memory"]["facts"] == ["f1"]


# === OpenHarness 7 类原生事件 transport 验证 ===

class TestNativeEvents:
    def test_assistant_text_delta_first_frame(self):
        """第一帧 delta 应自动注入 TextMessageStart。"""
        state = TransportState(thread_id="t1", run_id="r1")
        e = MockAssistantTextDelta(text="Hello")
        out = to_agui_events(e, state)
        assert len(out) == 2
        # 1. TextMessageStart (auto-injected)
        assert out[0]["type"] == "TEXT_MESSAGE_START"
        assert out[0]["role"] == "assistant"
        # 2. TextMessageContent
        assert out[1]["type"] == "TEXT_MESSAGE_CONTENT"
        assert out[1]["delta"] == "Hello"
        assert out[1]["messageId"] == out[0]["messageId"]
        # state 应被更新
        assert state.current_message_id is not None

    def test_assistant_text_delta_continuation(self):
        """第二帧 delta 不应重复注入 Start。"""
        state = TransportState(thread_id="t1", run_id="r1")
        # 第一帧
        to_agui_events(MockAssistantTextDelta(text="Hello "), state)
        # 第二帧
        out = to_agui_events(MockAssistantTextDelta(text="world"), state)
        assert len(out) == 1
        assert out[0]["type"] == "TEXT_MESSAGE_CONTENT"
        assert out[0]["delta"] == "world"

    def test_assistant_turn_complete(self):
        """AssistantTurnComplete 应 emit TextMessageEnd。"""
        state = TransportState(thread_id="t1", run_id="r1")
        # 先 start
        to_agui_events(MockAssistantTextDelta(text="Hi"), state)
        # turn complete
        out = to_agui_events(MockAssistantTurnComplete(), state)
        assert len(out) == 1
        assert out[0]["type"] == "TEXT_MESSAGE_END"
        # state 应清空
        assert state.current_message_id is None

    def test_assistant_turn_complete_without_start(self):
        """无 Start 直接 TurnComplete 应无输出。"""
        state = TransportState(thread_id="t1", run_id="r1")
        out = to_agui_events(MockAssistantTurnComplete(), state)
        assert out == []

    def test_tool_execution_started_three_piece(self):
        """ToolExecutionStarted 应 emit 3 件套（START/ARGS/END）。"""
        state = TransportState(thread_id="t1", run_id="r1")
        e = MockToolExecutionStarted(tool_name="ask_user_question",
                                      tool_input={"q": "是否继续？"})
        out = to_agui_events(e, state)
        assert len(out) == 3
        assert out[0]["type"] == "TOOL_CALL_START"
        assert out[0]["toolCallName"] == "ask_user_question"
        assert out[1]["type"] == "TOOL_CALL_ARGS"
        # delta 必须是 JSON 字符串
        assert isinstance(out[1]["delta"], str)
        assert "q" in out[1]["delta"]
        assert out[2]["type"] == "TOOL_CALL_END"
        # 三件套 ID 应一致
        assert out[0]["toolCallId"] == out[1]["toolCallId"] == out[2]["toolCallId"]
        # ID 应稳定（相同 input 相同 ID）
        expected_id = make_tool_call_id("ask_user_question", {"q": "是否继续？"})
        assert out[0]["toolCallId"] == expected_id

    def test_tool_execution_completed(self):
        """ToolExecutionCompleted 应 emit TOOL_CALL_RESULT。"""
        state = TransportState(thread_id="t1", run_id="r1")
        # 先 start
        to_agui_events(MockToolExecutionStarted(tool_name="bash",
                                                  tool_input={"cmd": "ls"}), state)
        # completed
        e = MockToolExecutionCompleted(tool_name="bash", output="file.txt\n")
        out = to_agui_events(e, state)
        assert len(out) == 1
        assert out[0]["type"] == "TOOL_CALL_RESULT"
        assert out[0]["content"] == "file.txt\n"
        assert out[0]["role"] == "tool"
        # ID 应与 start 一致
        expected_id = make_tool_call_id("bash", {"cmd": "ls"})
        assert out[0]["toolCallId"] == expected_id

    def test_error_event_recoverable(self):
        """可恢复 ErrorEvent 只发 RUN_ERROR。"""
        state = TransportState(thread_id="t1", run_id="r1")
        e = MockErrorEvent(message="rate limit hit", recoverable=True)
        out = to_agui_events(e, state)
        assert len(out) == 1
        assert out[0]["type"] == "RUN_ERROR"
        assert out[0]["message"] == "rate limit hit"

    def test_error_event_fatal(self):
        """不可恢复 ErrorEvent 应发 RUN_ERROR + RUN_FINISHED(error)。"""
        state = TransportState(thread_id="t1", run_id="r1")
        e = MockErrorEvent(message="internal crash", recoverable=False)
        out = to_agui_events(e, state)
        assert len(out) == 2
        assert out[0]["type"] == "RUN_ERROR"
        assert out[1]["type"] == "RUN_FINISHED"
        assert out[1]["outcome"]["type"] == "error"
        assert out[1]["outcome"]["error"] == "internal crash"

    def test_status_event(self):
        """StatusEvent → STEP_STARTED。"""
        state = TransportState(thread_id="t1", run_id="r1")
        e = MockStatusEvent(message="compacting context")
        out = to_agui_events(e, state)
        assert len(out) == 1
        assert out[0] == {"type": "STEP_STARTED", "stepName": "compacting context"}

    def test_compact_progress_event(self):
        """CompactProgressEvent → STATE_DELTA。"""
        state = TransportState(thread_id="t1", run_id="r1")
        e = MockCompactProgressEvent(phase="compact_start", trigger="auto",
                                      message="compacting", attempt=1)
        out = to_agui_events(e, state)
        assert len(out) == 1
        assert out[0]["type"] == "STATE_DELTA"
        delta = out[0]["delta"]
        assert isinstance(delta, list)
        assert len(delta) == 1
        assert delta[0]["op"] == "replace"
        assert delta[0]["path"] == "/compact"
        assert delta[0]["value"]["phase"] == "compact_start"


# === 状态机集成测试 ===

class TestStateMachineIntegration:
    def test_full_chat_flow(self):
        """完整对话流程：start → text → tool → result → end。"""
        state = TransportState(thread_id="t1", run_id="r1")
        events: list[dict[str, Any]] = []

        # 1. Run start
        events.extend(to_agui_events(
            RunStartedEvent(thread_id="t1", run_id="r1"), state
        ))

        # 2. First text delta
        events.extend(to_agui_events(MockAssistantTextDelta(text="Let me "), state))

        # 3. Second text delta
        events.extend(to_agui_events(MockAssistantTextDelta(text="check that."), state))

        # 4. Turn complete
        events.extend(to_agui_events(MockAssistantTurnComplete(), state))

        # 5. Tool call
        events.extend(to_agui_events(
            MockToolExecutionStarted(tool_name="query", tool_input={"q": "x"}), state
        ))

        # 6. Tool result
        events.extend(to_agui_events(
            MockToolExecutionCompleted(tool_name="query", output="answer"), state
        ))

        # 7. New turn start
        events.extend(to_agui_events(MockAssistantTextDelta(text="Found it."), state))
        events.extend(to_agui_events(MockAssistantTurnComplete(), state))

        # 8. Run finished
        events.extend(to_agui_events(
            RunFinishedEvent(thread_id="t1", run_id="r1", outcome="success"), state
        ))

        # Verify the event stream
        types = [e["type"] for e in events]
        assert types == [
            "RUN_STARTED",
            "TEXT_MESSAGE_START", "TEXT_MESSAGE_CONTENT", "TEXT_MESSAGE_CONTENT",
            "TEXT_MESSAGE_END",
            "TOOL_CALL_START", "TOOL_CALL_ARGS", "TOOL_CALL_END",
            "TOOL_CALL_RESULT",
            "TEXT_MESSAGE_START", "TEXT_MESSAGE_CONTENT", "TEXT_MESSAGE_END",
            "RUN_FINISHED",
        ]

    def test_state_cleanup_between_turns(self):
        """多 turn 应能正确清理 message_id 状态。"""
        state = TransportState(thread_id="t1", run_id="r1")
        # Turn 1
        to_agui_events(MockAssistantTextDelta(text="A"), state)
        to_agui_events(MockAssistantTurnComplete(), state)
        assert state.current_message_id is None

        # Turn 2 — 应能再次 start
        out = to_agui_events(MockAssistantTextDelta(text="B"), state)
        # 应有 Start + Content
        assert out[0]["type"] == "TEXT_MESSAGE_START"
        assert out[1]["type"] == "TEXT_MESSAGE_CONTENT"


# === SSE 编码验证 ===

class TestSSEEncoding:
    def test_encode_sse_basic(self):
        event = {"type": "RUN_STARTED", "threadId": "t1", "runId": "r1"}
        encoded = encode_sse(event)
        # 必须以 "data: " 开头 + 双换行结尾
        assert encoded.startswith("data: ")
        assert encoded.endswith("\n\n")
        # JSON 部分可被反序列化
        import json
        body = encoded[len("data: "):-2]
        decoded = json.loads(body)
        assert decoded["type"] == "RUN_STARTED"
        assert decoded["threadId"] == "t1"

    def test_encode_sse_with_unicode(self):
        """中文内容应正确编码。"""
        event = {"type": "TEXT_MESSAGE_CONTENT", "messageId": "m1", "delta": "你好"}
        encoded = encode_sse(event)
        import json
        body = encoded[len("data: "):-2]
        decoded = json.loads(body)
        assert decoded["delta"] == "你好"

    def test_encode_sse_complex_interrupts(self):
        """interrupt outcome 应正确编码。"""
        outcome = {
            "type": "interrupt",
            "interrupts": [
                {"id": "int-1", "reason": "confirmation", "message": "?"},
            ],
        }
        event = {"type": "RUN_FINISHED", "threadId": "t", "runId": "r", "outcome": outcome}
        encoded = encode_sse(event)
        import json
        body = encoded[len("data: "):-2]
        decoded = json.loads(body)
        assert decoded["outcome"]["type"] == "interrupt"
        assert decoded["outcome"]["interrupts"][0]["id"] == "int-1"


# === 边界 / 异常测试 ===

class TestEdgeCases:
    def test_unknown_event_silently_ignored(self):
        state = TransportState(thread_id="t1", run_id="r1")

        @dataclass
        class UnknownEvent:
            foo: str = "bar"

        out = to_agui_events(UnknownEvent(), state)
        assert out == []

    def test_tool_started_empty_input(self):
        """空 input 也应正常处理。"""
        state = TransportState(thread_id="t1", run_id="r1")
        e = MockToolExecutionStarted(tool_name="end", tool_input={})
        out = to_agui_events(e, state)
        assert len(out) == 3
        assert out[1]["delta"] == "{}"

    def test_tool_input_with_unicode(self):
        """中文 input 应被 JSON 序列化。"""
        state = TransportState(thread_id="t1", run_id="r1")
        e = MockToolExecutionStarted(tool_name="ask", tool_input={"q": "你好"})
        out = to_agui_events(e, state)
        import json
        args = json.loads(out[1]["delta"])
        assert args["q"] == "你好"

    def test_transport_state_isolation(self):
        """不同 TransportState 实例互不干扰。"""
        s1 = TransportState(thread_id="t1", run_id="r1")
        s2 = TransportState(thread_id="t2", run_id="r2")
        to_agui_events(MockAssistantTextDelta(text="A"), s1)
        assert s1.current_message_id is not None
        assert s2.current_message_id is None
