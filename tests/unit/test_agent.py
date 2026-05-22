import pytest
import sys
import os
import time
from unittest.mock import MagicMock, patch
from datetime import datetime, timezone

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..', '..'))

from odap.biz.agent.agent_factory import (
    TraceSpan, TracePhase, TraceStatus, Trace, TraceCollector,
    RoleManager, RoleConfig, RoleCapability, Capability, AgentFactory
)
from odap.biz.agent.router_v2 import (
    IntentRecognizer, SelfCorrector, AgentRouterV2, Intent, RoutingResult
)


class TestTraceSpan:
    def test_trace_span_creation(self):
        span = TraceSpan(
            span_id="span-001",
            parent_span_id=None,
            phase=TracePhase.INPUT,
            agent_type="intelligence",
            status=TraceStatus.RUNNING,
            input_data={"query": "test"},
            start_time=datetime.now(timezone.utc).isoformat(),
        )
        assert span.span_id == "span-001"
        assert span.parent_span_id is None
        assert span.phase == TracePhase.INPUT
        assert span.agent_type == "intelligence"
        assert span.status == TraceStatus.RUNNING
        assert span.input_data == {"query": "test"}
        assert span.output_data == {}
        assert span.end_time is None
        assert span.duration_ms == 0.0
        assert span.error_message is None
        assert span.metadata == {}

    def test_trace_span_complete(self):
        span = TraceSpan(
            span_id="span-002",
            parent_span_id=None,
            phase=TracePhase.OUTPUT,
            agent_type="commander",
            status=TraceStatus.RUNNING,
            start_time=datetime.now(timezone.utc).isoformat(),
        )
        span.complete(
            status=TraceStatus.SUCCESS,
            output={"result": "done"},
        )
        assert span.status == TraceStatus.SUCCESS
        assert span.end_time is not None
        assert span.duration_ms >= 0
        assert span.output_data == {"result": "done"}
        assert span.error_message is None

    def test_trace_span_to_dict(self):
        span = TraceSpan(
            span_id="span-003",
            parent_span_id="parent-001",
            phase=TracePhase.TOOL_CALL,
            agent_type="operations",
            status=TraceStatus.SUCCESS,
            input_data={"tool": "search"},
            output_data={"data": "found"},
            start_time="2025-01-01T00:00:00+00:00",
            end_time="2025-01-01T00:00:01+00:00",
            duration_ms=1000.0,
            metadata={"key": "value"},
        )
        d = span.to_dict()
        assert d["span_id"] == "span-003"
        assert d["parent_span_id"] == "parent-001"
        assert d["phase"] == "tool_call"
        assert d["agent_type"] == "operations"
        assert d["status"] == "success"
        assert d["input_data"] == {"tool": "search"}
        assert d["output_data"] == {"data": "found"}
        assert d["start_time"] == "2025-01-01T00:00:00+00:00"
        assert d["end_time"] == "2025-01-01T00:00:01+00:00"
        assert d["duration_ms"] == 1000.0
        assert d["error_message"] is None
        assert d["metadata"] == {"key": "value"}


class TestTrace:
    def test_trace_creation(self):
        trace = Trace(
            trace_id="trace-001",
            agent_id="agent-001",
            agent_type="intelligence",
        )
        assert trace.trace_id == "trace-001"
        assert trace.agent_id == "agent-001"
        assert trace.agent_type == "intelligence"
        assert trace.mission_id is None
        assert trace.spans == []
        assert trace.root_span_id is None
        assert trace.status == TraceStatus.PENDING
        assert trace.start_time is not None
        assert trace.end_time is None
        assert trace.total_duration_ms == 0.0

    def test_trace_create_span(self):
        trace = Trace(
            trace_id="trace-002",
            agent_id="agent-002",
            agent_type="commander",
        )
        span = trace.create_span(TracePhase.INPUT, input_data={"q": "hello"})
        assert span.phase == TracePhase.INPUT
        assert span.status == TraceStatus.RUNNING
        assert span.agent_type == "commander"
        assert span.input_data == {"q": "hello"}
        assert trace.root_span_id == span.span_id
        assert span in trace.spans

        span2 = trace.create_span(TracePhase.REASONING, parent_span_id=span.span_id)
        assert span2.parent_span_id == span.span_id
        assert trace.root_span_id == span.span_id

    def test_trace_complete(self):
        trace = Trace(
            trace_id="trace-003",
            agent_id="agent-003",
            agent_type="operations",
        )
        trace.complete(TraceStatus.SUCCESS)
        assert trace.status == TraceStatus.SUCCESS
        assert trace.end_time is not None
        assert trace.total_duration_ms >= 0


class TestTraceCollector:
    def test_start_trace(self):
        collector = TraceCollector()
        trace = collector.start_trace("agent-001", "intelligence", mission_id="m1")
        assert trace.agent_id == "agent-001"
        assert trace.agent_type == "intelligence"
        assert trace.mission_id == "m1"
        assert trace.trace_id is not None
        assert collector.get_trace(trace.trace_id) is not None

    def test_get_trace(self):
        collector = TraceCollector()
        trace = collector.start_trace("agent-002", "commander")
        found = collector.get_trace(trace.trace_id)
        assert found is trace
        assert collector.get_trace("nonexistent") is None

    def test_get_agent_traces(self):
        collector = TraceCollector()
        t1 = collector.start_trace("agent-003", "intelligence")
        t2 = collector.start_trace("agent-003", "intelligence")
        t3 = collector.start_trace("agent-004", "commander")
        traces = collector.get_agent_traces("agent-003")
        assert len(traces) == 2
        assert all(t.agent_id == "agent-003" for t in traces)
        traces_other = collector.get_agent_traces("agent-004")
        assert len(traces_other) == 1
        assert traces_other[0].agent_id == "agent-004"

    def test_get_stats(self):
        collector = TraceCollector()
        stats = collector.get_stats()
        assert stats == {"total": 0}

        t1 = collector.start_trace("agent-005", "intelligence")
        t1.complete(TraceStatus.SUCCESS)
        t2 = collector.start_trace("agent-006", "commander")
        t2.complete(TraceStatus.FAILED)

        stats = collector.get_stats()
        assert stats["total"] == 2
        assert stats["success"] == 1
        assert stats["failed"] == 1
        assert stats["success_rate"] == 50.0
        assert "intelligence" in stats["by_agent"]
        assert "commander" in stats["by_agent"]


class TestRoleManager:
    def test_init_default_roles(self):
        rm = RoleManager()
        roles = rm.get_all_roles()
        assert len(roles) == 3
        role_names = {r.role_name for r in roles}
        assert "Commander" in role_names
        assert "Intelligence" in role_names
        assert "Operations" in role_names

    def test_get_role(self):
        rm = RoleManager()
        commander = rm.get_role("commander")
        assert commander is not None
        assert commander.role_name == "Commander"
        assert commander.agent_type == "commander"
        assert rm.get_role("nonexistent") is None

    def test_has_capability(self):
        rm = RoleManager()
        assert rm.has_capability("commander", Capability.SITUATION_AWARENESS) is True
        assert rm.has_capability("commander", Capability.DECISION_MAKING) is True
        assert rm.has_capability("commander", Capability.TARGET_DETECTION) is False
        assert rm.has_capability("intelligence", Capability.THREAT_ANALYSIS) is True
        assert rm.has_capability("intelligence", Capability.TASK_EXECUTION) is False
        assert rm.has_capability("nonexistent", Capability.SITUATION_AWARENESS) is False

    def test_register_role(self):
        rm = RoleManager()
        custom_role = RoleConfig(
            role_name="CustomRole",
            agent_type="custom",
            description="A custom role for testing",
            capabilities=[
                RoleCapability(Capability.EXPLANATION),
            ],
            priority=1,
        )
        result = rm.register_role(custom_role)
        assert result is custom_role
        fetched = rm.get_role("customrole")
        assert fetched is not None
        assert fetched.role_name == "CustomRole"
        assert rm.has_capability("customrole", Capability.EXPLANATION) is True


class TestIntentRecognizer:
    def test_recognize_search(self):
        recognizer = IntentRecognizer()
        result = recognizer.recognize("搜索雷达目标")
        assert result.intent == Intent.SEARCH.value
        assert result.confidence > 0
        assert result.target_agent == "search_agent"

    def test_recognize_analysis(self):
        recognizer = IntentRecognizer()
        result = recognizer.recognize("分析当前态势")
        assert result.intent == Intent.ANALYSIS.value
        assert result.confidence > 0
        assert result.target_agent == "analysis_agent"

    def test_recognize_unknown(self):
        recognizer = IntentRecognizer()
        result = recognizer.recognize("xyzzy foobar")
        assert result.intent == Intent.UNKNOWN.value
        assert result.confidence == 0.0
        assert result.target_agent == "general"

    def test_map_intent_to_agent(self):
        recognizer = IntentRecognizer()
        assert recognizer._map_intent_to_agent(Intent.SEARCH.value) == "search_agent"
        assert recognizer._map_intent_to_agent(Intent.ANALYSIS.value) == "analysis_agent"
        assert recognizer._map_intent_to_agent(Intent.COMMAND.value) == "command_agent"
        assert recognizer._map_intent_to_agent(Intent.ATTACK.value) == "strike_agent"
        assert recognizer._map_intent_to_agent(Intent.QUERY.value) == "query_agent"
        assert recognizer._map_intent_to_agent(Intent.RECOMMEND.value) == "recommend_agent"
        assert recognizer._map_intent_to_agent(Intent.UNKNOWN.value) == "general_agent"


class TestSelfCorrector:
    def test_correct_denied_result(self):
        corrector = SelfCorrector()
        result = {"status": "denied", "message": "权限不足，无法执行此操作"}
        correction = corrector.correct(result, {"user_role": "pilot"})
        assert correction.corrected is True
        assert len(correction.corrections) > 0
        assert correction.original_result is result

    def test_correct_no_correction(self):
        corrector = SelfCorrector()
        result = {"status": "success", "data": {"key": "value"}}
        correction = corrector.correct(result, {})
        assert correction.corrected is False
        assert correction.corrections == []


class TestAgentRouterV2:
    @pytest.fixture(autouse=True)
    def _patch_orchestrator(self):
        with patch("odap.biz.agent.router_v2.SelfCorrectingOrchestratorV2"):
            self.router = AgentRouterV2(user_role="commander")

    def test_route_search(self):
        result = self.router.route("搜索雷达目标")
        assert result["success"] is True
        assert result["routing"]["intent"] == Intent.SEARCH.value
        assert result["routing"]["target_agent"] == "search_agent"

    def test_route_unknown(self):
        result = self.router.route("xyzzy foobar")
        assert result["routing"]["intent"] == Intent.UNKNOWN.value
        assert result["success"] is False

    def test_get_routing_history(self):
        self.router.route("搜索雷达目标")
        self.router.route("分析当前态势")
        history = self.router.get_routing_history()
        assert len(history) == 2
        assert history[0]["intent"] == Intent.ANALYSIS.value
        assert history[1]["intent"] == Intent.SEARCH.value
