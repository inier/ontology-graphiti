"""Unit tests for OntologyAppSkill and 4 engine skill adapters."""
import pytest

from odap.biz.core.ontology.application.ontology_app_skill import OntologyAppSkill
from odap.biz.core.ontology.application.runtime.skill_adapter import (
    RuntimeSkillAdapter, RuntimeSkillInput,
)
from odap.biz.core.ontology.application.servitization.skill_adapter import (
    ServitizationSkillAdapter, ServitizationSkillInput,
)
from odap.biz.core.ontology.application.team_agent.skill_adapter import (
    TeamAgentSkillAdapter, TeamAgentSkillInput,
)
from odap.biz.core.ontology.application.harness.skill_adapter import (
    HarnessSkillAdapter, HarnessSkillInput,
)
from odap.tools.base import SkillInput


class FakeRuntimeEngine:
    def __init__(self):
        self.calls = []

    def list_functions(self, function_type=None, target_object_type=None):
        self.calls.append(("list_functions", function_type, target_object_type))
        return {"status": "success", "functions": ["fn1", "fn2"], "count": 2}

    def execute_function(self, fn_id, ctx):
        self.calls.append(("execute_function", fn_id, ctx))
        return {"status": "success", "result": 42}


class FakeServitizationEngine:
    def list_services(self, status=None):
        return {"status": "success", "services": ["svc1"], "count": 1}

    def get_service(self, svc_id):
        return {"status": "success", "service_id": svc_id, "name": "test"}


class FakeTeamAgentEngine:
    def list_agents(self):
        return {"status": "success", "agents": ["a1"]}

    def dispatch_task(self, task):
        return {"status": "success", "task_id": "t-1", "task": task}


class FakeHarnessEngine:
    def list_sessions(self, status=None):
        return {"status": "success", "sessions": []}

    def create_session(self, **kwargs):
        return {"status": "success", "session_id": "s-1", **kwargs}


class TestOntologyAppSkill:
    def test_runtime_adapter_creation(self):
        adapter = RuntimeSkillAdapter(workspace_id="ws-1", ontology_id="ont-1")
        assert adapter.workspace_id == "ws-1"
        assert adapter.ontology_id == "ont-1"
        assert adapter.metadata.category == "ontology_app"
        assert not adapter._bound

    def test_runtime_bind_engine(self):
        engine = FakeRuntimeEngine()
        adapter = RuntimeSkillAdapter("ws", "ont")
        adapter.bind_engine(engine)
        assert adapter._bound

    def test_runtime_bind_engine_type_error(self):
        adapter = RuntimeSkillAdapter("ws", "ont")
        with pytest.raises(TypeError):
            adapter.bind_engine("not-an-engine")

    def test_runtime_execute_list(self):
        engine = FakeRuntimeEngine()
        adapter = RuntimeSkillAdapter("ws", "ont")
        adapter.bind_engine(engine)
        result = adapter.execute(RuntimeSkillInput(action="list_functions"))
        assert result.success
        assert result.data["count"] == 2

    def test_runtime_execute_unknown_action(self):
        engine = FakeRuntimeEngine()
        adapter = RuntimeSkillAdapter("ws", "ont")
        adapter.bind_engine(engine)
        result = adapter.execute(RuntimeSkillInput(action="invalid"))
        assert not result.success
        assert "Unknown" in result.error

    def test_runtime_execute_missing_function_id(self):
        engine = FakeRuntimeEngine()
        adapter = RuntimeSkillAdapter("ws", "ont")
        adapter.bind_engine(engine)
        result = adapter.execute(RuntimeSkillInput(action="execute_function"))
        assert not result.success
        assert "function_id" in result.error

    def test_engine_property_unbound(self):
        adapter = RuntimeSkillAdapter("ws", "ont")
        with pytest.raises(RuntimeError):
            _ = adapter.engine


class TestOtherAdapters:
    def test_servitization_adapter(self):
        engine = FakeServitizationEngine()
        adapter = ServitizationSkillAdapter("ws", "ont")
        adapter.bind_engine(engine)
        result = adapter.execute(SkillInput(action="list_services"))
        assert result.success
        result = adapter.execute(SkillInput(action="get_service", service_id="svc-1"))
        assert result.success

    def test_team_agent_adapter(self):
        engine = FakeTeamAgentEngine()
        adapter = TeamAgentSkillAdapter("ws", "ont")
        adapter.bind_engine(engine)
        result = adapter.execute(TeamAgentSkillInput(action="list_agents"))
        assert result.success
        result = adapter.execute(TeamAgentSkillInput(action="dispatch_task", task={"desc": "do it"}))
        assert result.success
        assert "task" in result.data, f"expected 'task' in {result.data}"
        assert result.data["task"]["workspace_id"] == "ws"

    def test_harness_adapter(self):
        engine = FakeHarnessEngine()
        adapter = HarnessSkillAdapter("ws", "ont")
        adapter.bind_engine(engine)
        result = adapter.execute(HarnessSkillInput(action="list_sessions"))
        assert result.success
        result = adapter.execute(HarnessSkillInput(action="create_session", session_name="s1", requirement="test"))
        assert result.success
        assert "workspace_id" in result.data, f"expected 'workspace_id' in {result.data}"
        assert result.data["workspace_id"] == "ws"
