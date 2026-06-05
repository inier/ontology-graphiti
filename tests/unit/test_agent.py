import pytest
import sys
import os
import time
import asyncio
from unittest.mock import MagicMock, patch
from datetime import datetime, timezone

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..', '..'))

from odap.biz.core.agent.agent_factory import (
    TraceSpan, TracePhase, TraceStatus, Trace, TraceCollector,
    RoleManager, RoleConfig, RoleCapability, Capability, AgentFactory
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


# ---------------------------------------------------------------------------
# TestIntentRouter — tests for odap.biz.core.agent.impl.intent_router.IntentRouter
# ---------------------------------------------------------------------------

class TestIntentRouter:
    """Tests for IntentRouter: rule registration, keyword routing, default fallback."""

    def _make_router(self):
        from odap.biz.core.agent.impl.intent_router import IntentRouter
        # Ensure LLM is not available so tests are deterministic
        with patch.dict(os.environ, {"OPENAI_API_KEY": "", "OPENAI_API_BASE": ""}):
            return IntentRouter()

    # -- register_rule -------------------------------------------------------

    def test_register_rule_basic(self):
        router = self._make_router()
        result = router.register_rule("custom_kw", "custom_role")
        assert result["status"] == "success"
        assert result["keyword"] == "custom_kw"
        assert result["role"] == "custom_role"

    def test_register_rule_case_insensitive(self):
        router = self._make_router()
        router.register_rule("MyKeyword", "my_role")
        # Internal map stores lowercase
        assert "mykeyword" in router._rule_map
        assert router._rule_map["mykeyword"] == "my_role"

    def test_register_rule_with_intent_type(self):
        from odap.biz.core.agent.impl.intent_router import IntentType
        router = self._make_router()
        router.register_rule("decide_now", "commander", intent_type=IntentType.DECISION)
        assert router._intent_type_map.get("decide_now") == IntentType.DECISION

    def test_register_rule_overwrite(self):
        router = self._make_router()
        router.register_rule("test_kw", "role_a")
        router.register_rule("test_kw", "role_b")
        assert router._rule_map["test_kw"] == "role_b"

    # -- route: Chinese keywords ---------------------------------------------

    def test_route_chinese_query(self):
        router = self._make_router()
        result = router.route("查询最新的数据")
        assert result["status"] == "success"
        assert result["intent_type"] == "query"
        assert result["target_role"] == "intelligence"
        assert result["method"] == "keyword"

    def test_route_chinese_analysis(self):
        router = self._make_router()
        result = router.route("分析当前趋势")
        assert result["intent_type"] == "analysis"
        assert result["target_role"] == "intelligence"

    def test_route_chinese_action(self):
        router = self._make_router()
        result = router.route("执行该操作")
        assert result["intent_type"] == "action"
        assert result["target_role"] == "operations"

    def test_route_chinese_decision(self):
        router = self._make_router()
        result = router.route("需要决策支持")
        assert result["intent_type"] == "decision"
        assert result["target_role"] == "commander"

    # -- route: English keywords ---------------------------------------------

    def test_route_english_query(self):
        router = self._make_router()
        result = router.route("query the database")
        assert result["intent_type"] == "query"
        assert result["target_role"] == "intelligence"

    def test_route_english_analyze(self):
        router = self._make_router()
        result = router.route("analyze the statistics")
        assert result["intent_type"] == "analysis"
        assert result["target_role"] == "intelligence"

    def test_route_english_create(self):
        router = self._make_router()
        result = router.route("create a new record")
        assert result["intent_type"] == "action"
        assert result["target_role"] == "operations"

    def test_route_english_decide(self):
        router = self._make_router()
        result = router.route("decide on the plan")
        assert result["intent_type"] == "decision"
        assert result["target_role"] == "commander"

    # -- route: rule-based (registered rules take priority) ------------------

    def test_route_rule_based_priority(self):
        router = self._make_router()
        router.register_rule("special", "special_role")
        result = router.route("do something special now")
        assert result["target_role"] == "special_role"
        assert result["method"] == "rule"
        assert result["confidence"] == 0.9

    # -- route: default fallback ---------------------------------------------

    def test_route_unknown_fallback(self):
        router = self._make_router()
        result = router.route("xyzzy nothing matches")
        assert result["status"] == "success"
        assert result["intent_type"] == "unknown"
        assert result["target_role"] == "intelligence"
        assert result["method"] == "default"
        assert result["confidence"] == 0.3

    # -- LLM fallback skipped when no API key --------------------------------

    def test_llm_not_available_without_api_key(self):
        router = self._make_router()
        assert router._llm_available is False

    # -- _intent_type_to_role static method ----------------------------------

    def test_intent_type_to_role_mapping(self):
        from odap.biz.core.agent.impl.intent_router import IntentType, IntentRouter
        assert IntentRouter._intent_type_to_role(IntentType.QUERY) == "intelligence"
        assert IntentRouter._intent_type_to_role(IntentType.ANALYSIS) == "intelligence"
        assert IntentRouter._intent_type_to_role(IntentType.ACTION) == "operations"
        assert IntentRouter._intent_type_to_role(IntentType.DECISION) == "commander"
        assert IntentRouter._intent_type_to_role(IntentType.UNKNOWN) == "intelligence"

    # -- confidence scaling with keyword count --------------------------------

    def test_route_confidence_increases_with_more_keywords(self):
        router = self._make_router()
        r1 = router.route("查询")
        r2 = router.route("查询 搜索 查找")
        assert r2["confidence"] >= r1["confidence"]


# ---------------------------------------------------------------------------
# TestOODALoop — tests for odap.biz.core.agent.impl.ooda_loop.OODALoop
# ---------------------------------------------------------------------------

class TestOODALoop:
    """Tests for OODALoop: observe, orient, decide, act phases."""

    def _make_loop(self, agent_id="test-agent", role="intelligence"):
        from odap.biz.core.agent.impl.ooda_loop import OODALoop
        return OODALoop(agent_id=agent_id, role=role)

    # -- full cycle ----------------------------------------------------------

    def test_run_full_cycle(self):
        loop = self._make_loop()
        context = {
            "observations": [{"content": "sensor reading", "source": "sensor"}],
            "query": "what is happening?",
        }
        result = asyncio.run(loop.run(context))
        assert result["status"] == "success"
        assert result["agent_id"] == "test-agent"
        assert result["role"] == "intelligence"
        assert "observe" in result
        assert "orient" in result
        assert "decide" in result
        assert "act" in result
        assert len(result["history"]) == 4

    # -- observe phase -------------------------------------------------------

    def test_observe_processes_observations_list(self):
        loop = self._make_loop()
        context = {
            "observations": [
                {"content": "obs1", "source": "s1"},
                {"content": "obs2", "source": "s2"},
            ],
        }
        result = asyncio.run(loop.run(context))
        obs = result["observe"]["observations"]
        assert len(obs) >= 2
        contents = [o["content"] for o in obs]
        assert "obs1" in contents
        assert "obs2" in contents

    def test_observe_adds_query(self):
        loop = self._make_loop()
        context = {"query": "hello world", "observations": []}
        result = asyncio.run(loop.run(context))
        obs = result["observe"]["observations"]
        assert any(o.get("content") == "hello world" for o in obs)

    def test_observe_handles_string_observations(self):
        loop = self._make_loop()
        context = {"observations": ["plain text obs"]}
        result = asyncio.run(loop.run(context))
        obs = result["observe"]["observations"]
        assert any(o.get("content") == "plain text obs" and o.get("source") == "input" for o in obs)

    def test_observe_handles_graph_data(self):
        loop = self._make_loop()
        context = {
            "observations": [],
            "graph_data": {"entities": ["e1", "e2", "e3"], "relationships": ["r1"]},
        }
        result = asyncio.run(loop.run(context))
        obs = result["observe"]["observations"]
        graph_obs = [o for o in obs if o.get("source") == "knowledge_graph"]
        assert len(graph_obs) == 1
        assert graph_obs[0]["entity_count"] == 3
        assert graph_obs[0]["relationship_count"] == 1

    # -- orient phase --------------------------------------------------------

    def test_orient_urgency_detection(self):
        loop = self._make_loop()
        context = {"observations": [{"content": "urgent situation detected", "source": "alert"}]}
        result = asyncio.run(loop.run(context))
        assert result["orient"]["analysis"]["urgency"] == "high"

    def test_orient_urgency_chinese(self):
        loop = self._make_loop()
        context = {"observations": [{"content": "紧急情况需要处理", "source": "alert"}]}
        result = asyncio.run(loop.run(context))
        assert result["orient"]["analysis"]["urgency"] == "high"

    def test_orient_data_completeness_sufficient(self):
        loop = self._make_loop()
        context = {
            "observations": [
                {"content": "obs1", "source": "s1"},
                {"content": "obs2", "source": "s2"},
                {"content": "obs3", "source": "knowledge_graph", "entity_count": 5, "relationship_count": 2},
            ],
        }
        result = asyncio.run(loop.run(context))
        assert result["orient"]["analysis"]["data_completeness"] == "sufficient"

    def test_orient_data_completeness_partial(self):
        loop = self._make_loop()
        context = {"observations": [{"content": "only one obs", "source": "s1"}]}
        result = asyncio.run(loop.run(context))
        assert result["orient"]["analysis"]["data_completeness"] == "partial"

    # -- decide phase --------------------------------------------------------

    def test_decide_empty_observations(self):
        loop = self._make_loop()
        context = {"observations": []}
        result = asyncio.run(loop.run(context))
        assert result["decide"]["decision"] == "request_more_data"
        assert result["decide"]["confidence"] == 0.2

    def test_decide_urgent_observations(self):
        loop = self._make_loop()
        context = {"observations": [{"content": "urgent: act now!", "source": "alert"}]}
        result = asyncio.run(loop.run(context))
        assert result["decide"]["decision"] == "act_immediately"
        assert result["decide"]["confidence"] == 0.7

    def test_decide_sufficient_data(self):
        loop = self._make_loop()
        context = {
            "observations": [
                {"content": "obs1", "source": "s1"},
                {"content": "obs2", "source": "s2"},
                {"content": "obs3", "source": "knowledge_graph", "entity_count": 2, "relationship_count": 1},
            ],
        }
        result = asyncio.run(loop.run(context))
        assert result["decide"]["decision"] == "proceed"
        assert result["decide"]["confidence"] == 0.85

    def test_decide_commander_role(self):
        loop = self._make_loop(role="commander")
        context = {
            "observations": [
                {"content": "obs1", "source": "s1"},
                {"content": "obs2", "source": "s2"},
                {"content": "obs3", "source": "knowledge_graph", "entity_count": 1, "relationship_count": 0},
            ],
        }
        result = asyncio.run(loop.run(context))
        assert result["decide"]["decision"] == "proceed_with_strategy"

    def test_decide_operations_role(self):
        loop = self._make_loop(role="operations")
        context = {
            "observations": [
                {"content": "obs1", "source": "s1"},
                {"content": "obs2", "source": "s2"},
                {"content": "obs3", "source": "knowledge_graph", "entity_count": 1, "relationship_count": 0},
            ],
        }
        result = asyncio.run(loop.run(context))
        assert result["decide"]["decision"] == "execute"

    # -- act phase -----------------------------------------------------------

    def test_act_request_more_data(self):
        loop = self._make_loop()
        context = {"observations": []}
        result = asyncio.run(loop.run(context))
        assert result["act"]["action"] == "gather_intelligence"
        assert result["act"]["result"] == "pending_data"

    def test_act_execute_task(self):
        loop = self._make_loop()
        context = {"observations": [{"content": "urgent task", "source": "alert"}]}
        result = asyncio.run(loop.run(context))
        assert result["act"]["action"] == "execute_task"
        assert result["act"]["result"] == "executing"

    def test_act_execute_with_monitoring(self):
        loop = self._make_loop()
        context = {
            "observations": [
                {"content": "obs1", "source": "s1"},
                {"content": "obs2", "source": "s2"},
                {"content": "obs3", "source": "knowledge_graph", "entity_count": 1, "relationship_count": 0},
            ],
        }
        result = asyncio.run(loop.run(context))
        assert result["act"]["action"] == "execute_with_monitoring"
        assert result["act"]["result"] == "in_progress"

    # -- history tracking ----------------------------------------------------

    def test_history_records_all_phases(self):
        loop = self._make_loop()
        context = {"observations": [{"content": "test", "source": "s1"}]}
        result = asyncio.run(loop.run(context))
        phases = [h["phase"] for h in result["history"]]
        assert phases == ["observe", "orient", "decide", "act"]


# ---------------------------------------------------------------------------
# TestDecisionChain — tests for odap.biz.core.agent.models.decision_chain
# ---------------------------------------------------------------------------

class TestDecisionChain:
    """Tests for DecisionPhase, DecisionStep, and DecisionChain models."""

    def test_decision_phase_values(self):
        from odap.biz.core.agent.models.decision_chain import DecisionPhase
        assert DecisionPhase.OBSERVE.value == "observe"
        assert DecisionPhase.ORIENT.value == "orient"
        assert DecisionPhase.DECIDE.value == "decide"
        assert DecisionPhase.ACT.value == "act"

    def test_decision_phase_is_str_enum(self):
        from odap.biz.core.agent.models.decision_chain import DecisionPhase
        assert isinstance(DecisionPhase.OBSERVE, str)
        assert DecisionPhase.OBSERVE == "observe"

    def test_decision_step_creation(self):
        from odap.biz.core.agent.models.decision_chain import DecisionStep, DecisionPhase
        step = DecisionStep(phase=DecisionPhase.OBSERVE, description="Initial observation")
        assert step.phase == DecisionPhase.OBSERVE
        assert step.description == "Initial observation"
        assert step.step_id != ""
        assert step.evidence == []
        assert step.timestamp is not None

    def test_decision_step_with_evidence(self):
        from odap.biz.core.agent.models.decision_chain import DecisionStep, DecisionPhase
        step = DecisionStep(
            phase=DecisionPhase.DECIDE,
            description="Made a decision",
            evidence=[{"type": "data", "value": 42}],
        )
        assert len(step.evidence) == 1
        assert step.evidence[0]["value"] == 42

    def test_decision_step_required_fields(self):
        from odap.biz.core.agent.models.decision_chain import DecisionStep
        with pytest.raises(Exception):
            DecisionStep()  # phase is required

    def test_decision_chain_creation(self):
        from odap.biz.core.agent.models.decision_chain import DecisionChain
        chain = DecisionChain(task_id="task-001")
        assert chain.task_id == "task-001"
        assert chain.decision_id != ""
        assert chain.steps == []
        assert chain.reasoning == ""
        assert chain.evidence == []
        assert chain.workspace_id is None

    def test_decision_chain_default_factory_steps(self):
        from odap.biz.core.agent.models.decision_chain import DecisionChain, DecisionStep, DecisionPhase
        chain1 = DecisionChain()
        chain2 = DecisionChain()
        chain1.steps.append(DecisionStep(phase=DecisionPhase.ACT))
        assert len(chain1.steps) == 1
        assert len(chain2.steps) == 0  # independent lists

    def test_decision_chain_default_factory_evidence(self):
        from odap.biz.core.agent.models.decision_chain import DecisionChain
        chain1 = DecisionChain()
        chain2 = DecisionChain()
        chain1.evidence.append({"key": "val"})
        assert len(chain1.evidence) == 1
        assert len(chain2.evidence) == 0

    def test_decision_chain_json_serialization(self):
        from odap.biz.core.agent.models.decision_chain import DecisionChain, DecisionStep, DecisionPhase
        step = DecisionStep(phase=DecisionPhase.OBSERVE, description="test step")
        chain = DecisionChain(
            task_id="t1",
            steps=[step],
            reasoning="test reasoning",
        )
        data = chain.model_dump()
        # Verify str(Enum) serializes as string value, not enum object
        assert data["steps"][0]["phase"] == "observe"
        assert isinstance(data["steps"][0]["phase"], str)

    def test_decision_chain_from_dict_roundtrip(self):
        from odap.biz.core.agent.models.decision_chain import DecisionChain, DecisionStep, DecisionPhase
        step = DecisionStep(phase=DecisionPhase.DECIDE, description="decide step")
        chain = DecisionChain(task_id="t2", steps=[step], reasoning="r")
        data = chain.model_dump()
        restored = DecisionChain.model_validate(data)
        assert restored.task_id == "t2"
        assert len(restored.steps) == 1
        assert restored.steps[0].phase == DecisionPhase.DECIDE


# ---------------------------------------------------------------------------
# TestAgentConfig — tests for odap.biz.core.agent.models.agent_config
# ---------------------------------------------------------------------------

class TestAgentConfig:
    """Tests for AgentRole enum and AgentConfig model."""

    def test_agent_role_values(self):
        from odap.biz.core.agent.models.agent_config import AgentRole
        assert AgentRole.COMMANDER.value == "commander"
        assert AgentRole.INTELLIGENCE.value == "intelligence"
        assert AgentRole.OPERATIONS.value == "operations"

    def test_agent_role_is_str_enum(self):
        from odap.biz.core.agent.models.agent_config import AgentRole
        assert isinstance(AgentRole.COMMANDER, str)
        assert AgentRole.COMMANDER == "commander"

    def test_agent_config_creation_defaults(self):
        from odap.biz.core.agent.models.agent_config import AgentConfig, AgentRole
        config = AgentConfig()
        assert config.agent_id == ""
        assert config.name == ""
        assert config.role == AgentRole.INTELLIGENCE
        assert config.workspace_id == ""
        assert config.description == ""
        assert config.skills == []
        assert config.config == {}

    def test_agent_config_creation_with_values(self):
        from odap.biz.core.agent.models.agent_config import AgentConfig, AgentRole
        config = AgentConfig(
            agent_id="a1",
            name="TestAgent",
            role=AgentRole.COMMANDER,
            workspace_id="ws1",
            description="A test agent",
            skills=["skill1", "skill2"],
            config={"temperature": 0.7},
        )
        assert config.agent_id == "a1"
        assert config.name == "TestAgent"
        assert config.role == AgentRole.COMMANDER
        assert config.workspace_id == "ws1"
        assert config.skills == ["skill1", "skill2"]
        assert config.config == {"temperature": 0.7}

    def test_agent_config_default_factory_skills(self):
        from odap.biz.core.agent.models.agent_config import AgentConfig
        c1 = AgentConfig()
        c2 = AgentConfig()
        c1.skills.append("new_skill")
        assert len(c1.skills) == 1
        assert len(c2.skills) == 0  # independent lists

    def test_agent_config_default_factory_config(self):
        from odap.biz.core.agent.models.agent_config import AgentConfig
        c1 = AgentConfig()
        c2 = AgentConfig()
        c1.config["key"] = "val"
        assert c1.config == {"key": "val"}
        assert c2.config == {}  # independent dicts

    def test_agent_config_json_serialization(self):
        from odap.biz.core.agent.models.agent_config import AgentConfig, AgentRole
        config = AgentConfig(agent_id="a2", role=AgentRole.OPERATIONS)
        data = config.model_dump()
        # str(Enum) serializes as plain string
        assert data["role"] == "operations"
        assert isinstance(data["role"], str)


