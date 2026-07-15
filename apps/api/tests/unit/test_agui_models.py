"""Unit tests for AG-UI Pydantic models.

Per AGENTS.md 规则 9: 新增模块必须测试。
Per plan v2.0 T007: 验证 Pydantic 序列化/反序列化、enum 值、camelCase 字段名。
"""

from __future__ import annotations

import json
from datetime import datetime

import pytest
from pydantic import ValidationError

from odap.infra.openharness.agui.agui_models import (
    AGUIEventType,
    ActivitySnapshotEvent,
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
)


# === 规则 4 验证：Enum 必须 (str, Enum) ===

class TestEnums:
    def test_interrupt_reason_str_values(self):
        """InterruptReason 必须 (str, Enum) 双继承，value 必须是字符串。"""
        assert str(InterruptReason.CONFIRMATION) == "InterruptReason.CONFIRMATION"
        assert InterruptReason.CONFIRMATION.value == "confirmation"
        assert InterruptReason.TOOL_CALL.value == "tool_call"

    def test_card_type_str_values(self):
        """CardType 7 个内置值。"""
        assert {c.value for c in CardType} == {
            "chart", "graph", "temporal", "report_link", "action", "confirm", "input",
        }

    def test_interrupt_status_str_values(self):
        assert InterruptStatus.RESOLVED.value == "resolved"
        assert InterruptStatus.CANCELLED.value == "cancelled"

    def test_agui_event_type_str_values(self):
        """17 类 AGUIEventType。"""
        assert len(list(AGUIEventType)) >= 16


# === 规则 5 验证：容器字段必须 Field(default_factory=...) ===

class TestContainerDefaults:
    def test_run_agent_input_defaults(self):
        """RunAgentInput 容器字段应使用 default_factory。"""
        ri = RunAgentInput(threadId="t1", runId="r1")
        # 各列表字段应该是新 list 实例（不是 [] 共享）
        assert ri.messages == []
        assert ri.tools == []
        assert ri.context == []
        assert ri.state == {}
        assert ri.resume == []
        # 两次实例化不应共享 list
        ri2 = RunAgentInput(threadId="t2", runId="r2")
        ri.messages.append({"x": 1})
        assert ri2.messages == []  # 互相隔离

    def test_state_snapshot_default(self):
        ss = StateSnapshotEvent()
        assert ss.snapshot == {}
        # 隔离
        ss2 = StateSnapshotEvent()
        ss.snapshot["x"] = 1
        assert ss2.snapshot == {}

    def test_state_delta_default(self):
        sd = StateDeltaEvent()
        assert sd.delta == []


# === camelCase 字段名验证（AG-UI 协议要求） ===

class TestCamelCaseFields:
    def test_run_started_camel_case(self):
        """AG-UI 协议字段名必须保持 camelCase。"""
        e = RunStartedEvent(threadId="t", runId="r")
        d = e.model_dump(by_alias=False)  # 默认就用定义名
        assert "threadId" in d
        assert "runId" in d
        assert "parentRunId" in d
        assert "input" in d

    def test_run_started_json_serialization(self):
        """model_dump_json 输出 JSON 字段名应与定义一致。"""
        e = RunStartedEvent(threadId="t", runId="r", parentRunId="p")
        j = e.model_dump_json()
        loaded = json.loads(j)
        assert loaded["type"] == "RUN_STARTED"
        assert loaded["threadId"] == "t"
        assert loaded["runId"] == "r"
        assert loaded["parentRunId"] == "p"

    def test_text_message_content_delta(self):
        e = TextMessageContentEvent(messageId="m1", delta="hello")
        d = e.model_dump()
        assert d["delta"] == "hello"
        assert d["messageId"] == "m1"
        assert d["type"] == "TEXT_MESSAGE_CONTENT"

    def test_tool_call_args_delta_string(self):
        """TOOL_CALL_ARGS delta 必须是字符串（JSON 序列化）。"""
        e = ToolCallArgsEvent(toolCallId="tc1", delta='{"key": "val"}')
        d = e.model_dump()
        assert isinstance(d["delta"], str)
        assert "key" in d["delta"]


# === type 字段字面量值验证 ===

class TestTypeLiteral:
    def test_run_started_type(self):
        e = RunStartedEvent(threadId="t", runId="r")
        assert e.type == "RUN_STARTED"

    def test_run_finished_type(self):
        e = RunFinishedEvent(threadId="t", runId="r", outcome="success")
        assert e.type == "RUN_FINISHED"

    def test_text_message_types(self):
        assert TextMessageStartEvent(messageId="m").type == "TEXT_MESSAGE_START"
        assert TextMessageContentEvent(messageId="m", delta="x").type == "TEXT_MESSAGE_CONTENT"
        assert TextMessageEndEvent(messageId="m").type == "TEXT_MESSAGE_END"

    def test_tool_call_types(self):
        assert ToolCallStartEvent(toolCallId="t", toolCallName="n").type == "TOOL_CALL_START"
        assert ToolCallArgsEvent(toolCallId="t", delta="x").type == "TOOL_CALL_ARGS"
        assert ToolCallEndEvent(toolCallId="t").type == "TOOL_CALL_END"
        assert ToolCallResultEvent(messageId="m", toolCallId="t", content="x").type == "TOOL_CALL_RESULT"


# === RunAgentInput 完整验证 ===

class TestRunAgentInput:
    def test_minimal(self):
        ri = RunAgentInput(threadId="t1", runId="r1")
        assert ri.threadId == "t1"
        assert ri.runId == "r1"
        assert ri.parentRunId is None
        assert ri.messages == []
        assert ri.tools == []
        assert ri.resume == []
        # ODAP 扩展字段
        assert ri.workspaceId is None
        assert ri.userId is None
        assert ri.model is None

    def test_with_messages(self):
        msgs = [Message(id="m1", role="user", content="hi")]
        ri = RunAgentInput(threadId="t", runId="r", messages=msgs)
        assert len(ri.messages) == 1
        assert ri.messages[0].role == "user"

    def test_with_resume(self):
        resume = [ResumeEntry(
            interruptId="int-1",
            status=InterruptStatus.RESOLVED,
            response={"approved": True},
        )]
        ri = RunAgentInput(threadId="t", runId="r", resume=resume)
        assert ri.resume[0].interruptId == "int-1"
        assert ri.resume[0].response == {"approved": True}

    def test_required_fields(self):
        """threadId / runId 必填。"""
        with pytest.raises(ValidationError):
            RunAgentInput()  # type: ignore
        with pytest.raises(ValidationError):
            RunAgentInput(threadId="t")  # type: ignore

    def test_json_round_trip(self):
        """JSON 序列化 → 反序列化 应保留数据。"""
        ri = RunAgentInput(
            threadId="t-001",
            runId="r-001",
            parentRunId="r-000",
            messages=[Message(id="m1", role="user", content="hi")],
            state={"memory": {"facts": ["f1"]}},
        )
        j = ri.model_dump_json()
        loaded = RunAgentInput.model_validate_json(j)
        assert loaded.threadId == "t-001"
        assert loaded.parentRunId == "r-000"
        assert loaded.messages[0].content == "hi"
        assert loaded.state == {"memory": {"facts": ["f1"]}}


# === Interrupt 完整验证 ===

class TestInterrupt:
    def test_confirm_interrupt(self):
        """HITL 确认型 interrupt。"""
        i = Interrupt(
            id="int-1",
            reason=InterruptReason.CONFIRMATION,
            message="是否继续？",
            responseSchema={"type": "object", "properties": {"approved": {"type": "boolean"}}},
        )
        d = i.model_dump()
        assert d["reason"] == "confirmation"
        assert d["message"] == "是否继续？"
        assert "approved" in d["responseSchema"]["properties"]

    def test_tool_call_interrupt(self):
        """危险工具拦截 interrupt。"""
        i = Interrupt(
            id="int-2",
            reason=InterruptReason.TOOL_CALL,
            message="agent 想要执行 rm -rf",
            toolCallId="tc-001",
        )
        d = i.model_dump()
        assert d["reason"] == "tool_call"
        assert d["toolCallId"] == "tc-001"

    def test_input_required_interrupt(self):
        i = Interrupt(
            id="int-3",
            reason=InterruptReason.INPUT_REQUIRED,
            message="请输入名称",
        )
        d = i.model_dump()
        assert d["reason"] == "input_required"

    def test_metadata_default(self):
        """metadata 应有 default_factory=dict。"""
        i = Interrupt(id="x", reason=InterruptReason.CONFIRMATION, message="m")
        assert i.metadata == {}
        # 隔离
        i2 = Interrupt(id="y", reason=InterruptReason.CONFIRMATION, message="m")
        i.metadata["k"] = "v"
        assert i2.metadata == {}


# === StateDeltaOp JSON Patch 验证 ===

class TestStateDeltaOp:
    def test_replace_op(self):
        op = StateDeltaOp(op="replace", path="/compact/phase", value="done")
        # exclude_none: AG-UI 协议 wire format 中 None 字段不出现
        d = op.model_dump(by_alias=True, exclude_none=True)
        assert d["op"] == "replace"
        assert d["path"] == "/compact/phase"
        assert d["value"] == "done"
        assert "from" not in d

    def test_move_op_with_from(self):
        op = StateDeltaOp(op="move", path="/new", from_="/old", value=None)  # type: ignore
        d = op.model_dump(by_alias=True)
        assert d["op"] == "move"
        assert d["from"] == "/old"


# === Message 验证 ===

class TestMessage:
    def test_minimal(self):
        m = Message(id="m1", role="user")
        assert m.content is None
        assert m.toolCallId is None

    def test_tool_message(self):
        m = Message(id="m1", role="tool", content="result", toolCallId="tc1")
        d = m.model_dump()
        assert d["role"] == "tool"
        assert d["toolCallId"] == "tc1"

    def test_with_timestamp(self):
        now = datetime.now()
        m = Message(id="m1", role="assistant", content="hi", createdAt=now)
        d = m.model_dump()
        assert d["createdAt"] == now

    def test_role_literal(self):
        """role 必须是枚举的字面量。"""
        with pytest.raises(ValidationError):
            Message(id="m1", role="invalid")  # type: ignore


# === Card 验证 ===

class TestCardMetadata:
    def test_chart_card(self):
        cm = CardMetadata(
            card_type=CardType.CHART,
            card_props={"data": [1, 2, 3], "type": "line"},
        )
        d = cm.model_dump()
        assert d["card_type"] == CardType.CHART
        assert d["card_props"]["type"] == "line"


# === MessagesSnapshot 验证 ===

class TestMessagesSnapshot:
    def test_empty(self):
        ms = MessagesSnapshotEvent()
        assert ms.messages == []

    def test_with_messages(self):
        ms = MessagesSnapshotEvent(messages=[
            Message(id="m1", role="user", content="hi"),
            Message(id="m2", role="assistant", content="hello"),
        ])
        assert len(ms.messages) == 2


# === RunFinishedOutcome 验证 ===

class TestRunFinishedOutcome:
    def test_success_outcome(self):
        outcome = RunFinishedOutcome(outcome_type="success", result={"usage": {"tokens": 100}})
        j = outcome.to_json()
        assert j["type"] == "success"
        assert j["result"]["usage"]["tokens"] == 100

    def test_interrupt_outcome(self):
        outcome = RunFinishedOutcome(
            outcome_type="interrupt",
            interrupts=[Interrupt(id="int-1", reason=InterruptReason.CONFIRMATION, message="?")],
        )
        j = outcome.to_json()
        assert j["type"] == "interrupt"
        assert len(j["interrupts"]) == 1
        assert j["interrupts"][0]["id"] == "int-1"
        assert j["interrupts"][0]["reason"] == "confirmation"

    def test_error_outcome(self):
        outcome = RunFinishedOutcome(outcome_type="error", error="OpenAI rate limit")
        j = outcome.to_json()
        assert j["type"] == "error"
        assert j["error"] == "OpenAI rate limit"


# === Step 事件验证 ===

class TestStepEvents:
    def test_step_started(self):
        e = StepStartedEvent(stepName="query")
        d = e.model_dump()
        assert d["type"] == "STEP_STARTED"
        assert d["stepName"] == "query"

    def test_step_finished(self):
        e = StepFinishedEvent(stepName="compact")
        d = e.model_dump()
        assert d["type"] == "STEP_FINISHED"


# === ActivitySnapshot 验证 ===

class TestActivitySnapshot:
    def test_empty(self):
        e = ActivitySnapshotEvent()
        assert e.activity == []


# === ToolCall 事件验证 ===

class TestToolCallEvents:
    def test_start(self):
        e = ToolCallStartEvent(toolCallId="tc1", toolCallName="bash", parentMessageId="m1")
        d = e.model_dump()
        assert d["toolCallId"] == "tc1"
        assert d["toolCallName"] == "bash"
        assert d["parentMessageId"] == "m1"

    def test_chunk(self):
        e = ToolCallChunkEvent(toolCallId="tc1", delta="partial")
        d = e.model_dump()
        assert d["delta"] == "partial"

    def test_result(self):
        e = ToolCallResultEvent(messageId="m1", toolCallId="tc1", content="done")
        d = e.model_dump()
        assert d["type"] == "TOOL_CALL_RESULT"
        assert d["role"] == "tool"
        assert d["content"] == "done"


# === Context 验证 ===

class TestContext:
    def test_optional_fields(self):
        c = Context()
        assert c.description is None
        assert c.value is None

    def test_with_value(self):
        c = Context(description="workspace", value={"ws_id": "ws-1"})
        d = c.model_dump()
        assert d["description"] == "workspace"
        assert d["value"]["ws_id"] == "ws-1"


# === Tool 验证 ===

class TestTool:
    def test_minimal(self):
        t = Tool(name="confirm", description="confirm action")
        d = t.model_dump()
        assert d["name"] == "confirm"
        assert d["parameters"] == {}


# === RunErrorEvent 验证 ===

class TestRunError:
    def test_minimal(self):
        e = RunErrorEvent(message="internal error")
        d = e.model_dump()
        assert d["type"] == "RUN_ERROR"
        assert d["message"] == "internal error"
        assert d["code"] is None

    def test_with_code(self):
        e = RunErrorEvent(message="rate limit", code="OPENAI_RATE_LIMIT")
        d = e.model_dump()
        assert d["code"] == "OPENAI_RATE_LIMIT"


# === StateSnapshot 验证 ===

class TestStateSnapshot:
    def test_memory_state(self):
        ss = StateSnapshotEvent(snapshot={
            "memory": {"facts": ["f1", "f2"]},
            "active_skills": ["ask_user_question", "bash"],
        })
        d = ss.model_dump()
        assert d["snapshot"]["memory"]["facts"] == ["f1", "f2"]
        assert "ask_user_question" in d["snapshot"]["active_skills"]


# === 集成测试：AG-UI 协议 wire format 验证 ===

class TestWireFormat:
    """验证模型输出与 AG-UI 协议规格一致。"""

    def test_run_started_wire(self):
        """client 收到的第一个事件是 RUN_STARTED。"""
        e = RunStartedEvent(threadId="t", runId="r")
        wire = json.loads(e.model_dump_json())
        assert wire["type"] == "RUN_STARTED"
        assert wire["threadId"] == "t"
        assert wire["runId"] == "r"

    def test_message_three_piece(self):
        """TEXT_MESSAGE_START/CONTENT/END 三件套。"""
        s = TextMessageStartEvent(messageId="m1")
        c = TextMessageContentEvent(messageId="m1", delta="hello")
        e = TextMessageEndEvent(messageId="m1")
        assert s.messageId == c.messageId == e.messageId == "m1"

    def test_tool_call_three_piece(self):
        """TOOL_CALL_START/ARGS/END 三件套。"""
        s = ToolCallStartEvent(toolCallId="tc1", toolCallName="ask_user_question")
        a = ToolCallArgsEvent(toolCallId="tc1", delta='{"q":"continue?"}')
        e = ToolCallEndEvent(toolCallId="tc1")
        assert s.toolCallId == a.toolCallId == e.toolCallId == "tc1"

    def test_interrupt_in_outcome(self):
        """RunFinishedEvent.outcome 是 dict 时，含 interrupts[]。"""
        outcome_dict = {
            "type": "interrupt",
            "interrupts": [
                {"id": "int-1", "reason": "confirmation", "message": "?"},
            ],
        }
        e = RunFinishedEvent(threadId="t", runId="r", outcome=outcome_dict)
        d = e.model_dump()
        assert d["outcome"]["type"] == "interrupt"
        assert d["outcome"]["interrupts"][0]["reason"] == "confirmation"

    def test_run_agent_input_ag_ui_compatible(self):
        """RunAgentInput 兼容 AG-UI RunAgentInput schema。"""
        ri = RunAgentInput(
            threadId="thread-1",
            runId="run-1",
            messages=[Message(id="m1", role="user", content="hi")],
            tools=[Tool(name="confirm", description="d")],
        )
        wire = json.loads(ri.model_dump_json())
        # 关键字段必须在顶层
        assert "threadId" in wire
        assert "runId" in wire
        assert "messages" in wire
        assert "tools" in wire
        assert "state" in wire
        assert "resume" in wire
