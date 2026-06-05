"""
Simulation 端到端工作流测试
T294: 验证事件模拟→策略推演→沙箱模拟→反馈闭环的完整跨模块工作流
"""

import pytest
import sys
import os
import uuid
from unittest.mock import MagicMock, patch, AsyncMock
from datetime import datetime, timedelta

project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if project_root not in sys.path:
    sys.path.insert(0, project_root)

pytestmark = pytest.mark.e2e


@pytest.fixture
def event_service():
    from odap.biz.simulation.event_simulator.services.simulator_service import EventSimulatorService
    return EventSimulatorService()


@pytest.fixture
def deduction_service():
    from odap.biz.simulation.simulation_deduction.services.deduction_service import DeductionService
    return DeductionService()


@pytest.fixture
def sandbox_service():
    from odap.biz.simulation.simulation_sandbox.services.sandbox_service import SandboxService
    return SandboxService()


@pytest.fixture
def feedback_loop():
    from odap.biz.simulation.feedback.loop import FeedbackLoop
    return FeedbackLoop()


class TestEventSimulatorWorkflow:
    """事件模拟器工作流测试"""

    def test_template_create_list_delete(self, event_service):
        template = event_service.create_template(
            name="e2e-test-template",
            event_type="test_event",
            description="E2E test template",
            data_schema={"type": "object", "properties": {"severity": {"type": "string"}}}
        )
        assert template["status"] == "success"
        template_id = template["template_id"]

        templates = event_service.list_templates()
        assert len(templates) >= 1

        found = [t for t in templates if t.get("template_id") == template_id or t.get("id") == template_id]
        assert len(found) >= 1

    def test_time_control_workflow(self, event_service):
        tc = event_service.set_time_control(speed=2.0, is_paused=False)
        assert tc["status"] == "success"

        current = event_service.get_time_control()
        assert current is not None

        advanced = event_service.advance_clock(delta_seconds=60)
        assert advanced["status"] == "success"


class TestDeductionWorkflow:
    """策略推演工作流测试"""

    def test_create_and_list_scenario(self, deduction_service):
        scenario = deduction_service.create_scenario(
            name="e2e-deduction-scenario",
            description="E2E test scenario"
        )
        assert scenario["status"] == "success"
        assert "scenario_id" in scenario

        scenarios = deduction_service.list_scenarios()
        assert len(scenarios.get("scenarios", scenarios.get("items", []))) >= 1

    def test_scenario_with_conditions_and_chains(self, deduction_service):
        scenario = deduction_service.create_scenario(
            name="e2e-conditions-scenario",
            description="E2E conditions test"
        )
        scenario_id = scenario["scenario_id"]

        conditions = deduction_service.load_ontology_conditions(scenario_id)
        assert conditions["status"] == "success"

        chain = deduction_service.add_execution_chain(
            scenario_id=scenario_id,
            name="test-chain",
            description="Test chain",
            steps=[{
                "step_order": 1,
                "action_type_id": "action-1",
                "target_object_id": "obj-1",
                "target_object_type": "entity",
                "parameters": {"factor": 1.5},
                "conditions": [],
                "description": "Step 1"
            }],
            conditions=[]
        )
        assert chain["status"] == "success"

        simulate = deduction_service.simulate_chain(scenario_id, chain["chain_id"])
        assert simulate["status"] == "success"

    def test_simulate_all_and_compare(self, deduction_service):
        scenario = deduction_service.create_scenario(
            name="e2e-compare-scenario",
            description="E2E compare test"
        )
        scenario_id = scenario["scenario_id"]

        chain_a = deduction_service.add_execution_chain(
            scenario_id=scenario_id,
            name="chain-a",
            steps=[{"step_order": 1, "action_type_id": "a1", "target_object_id": "o1",
                     "target_object_type": "entity", "parameters": {}, "conditions": [], "description": "A"}],
            conditions=[]
        )
        chain_b = deduction_service.add_execution_chain(
            scenario_id=scenario_id,
            name="chain-b",
            steps=[{"step_order": 1, "action_type_id": "b1", "target_object_id": "o1",
                     "target_object_type": "entity", "parameters": {}, "conditions": [], "description": "B"}],
            conditions=[]
        )

        all_result = deduction_service.simulate_all_chains(scenario_id)
        assert all_result["status"] == "success"

        compare = deduction_service.compare_chains(
            scenario_id=scenario_id,
            chain_ids=[chain_a["chain_id"], chain_b["chain_id"]]
        )
        assert compare["status"] == "success"


class TestSandboxWorkflow:
    """沙箱模拟工作流测试"""

    def test_create_run_and_destroy_sandbox(self, sandbox_service):
        sandbox = sandbox_service.create_sandbox(config={
            "max_memory_mb": 512,
            "max_time_seconds": 30,
            "workspace_id": "ws-e2e-001"
        })
        assert sandbox["status"] == "success"
        sandbox_id = sandbox["sandbox_id"]

        run = sandbox_service.run_simulation(
            sandbox_id=sandbox_id,
            params={
                "action_type_id": "action-e2e",
                "target_object_id": "obj-e2e",
                "target_object_type": "entity",
                "parameters": {"factor": 2.0}
            }
        )
        assert run["status"] == "success"

        status = sandbox_service.get_sandbox_status(sandbox_id)
        assert status is not None

        results = sandbox_service.get_sandbox_results(sandbox_id)
        assert results is not None

        destroy = sandbox_service.destroy_sandbox(sandbox_id)
        assert destroy["status"] == "success"

    def test_sandbox_export_results(self, sandbox_service):
        sandbox = sandbox_service.create_sandbox(config={
            "max_memory_mb": 256,
            "max_time_seconds": 10,
            "workspace_id": "ws-e2e-002"
        })
        sandbox_id = sandbox["sandbox_id"]

        sandbox_service.run_simulation(
            sandbox_id=sandbox_id,
            params={
                "action_type_id": "action-export",
                "target_object_id": "obj-export",
                "target_object_type": "entity",
                "parameters": {}
            }
        )

        export = sandbox_service.export_results(sandbox_id, approved_by="admin")
        assert export["status"] == "success"

        sandbox_service.destroy_sandbox(sandbox_id)


class TestFeedbackWorkflow:
    """反馈闭环工作流测试"""

    def test_collect_and_analyze_feedback(self, feedback_loop):
        source_id = str(uuid.uuid4())

        feedback = feedback_loop.collect_feedback(
            source_id=source_id,
            feedback_type="action_result",
            outcome="partial_success",
            data={"expected": 100, "actual": 85}
        )
        assert feedback is not None
        assert feedback.source_id == source_id

    def test_close_feedback_loop(self, feedback_loop):
        source_id = str(uuid.uuid4())

        feedback = feedback_loop.collect_feedback(
            source_id=source_id,
            feedback_type="decision_feedback",
            outcome="deviation",
            data={"deviation_score": 0.3}
        )

        result = feedback_loop.close_loop(feedback)
        assert result["status"] == "success"

    def test_aggregate_feedback(self, feedback_loop):
        ontology_id = str(uuid.uuid4())

        for i in range(3):
            feedback_loop.collect_feedback(
                source_id=f"agg-source-{i}",
                feedback_type="outcome_deviation",
                outcome="deviation",
                data={"score": 0.1 * i}
            )

        result = feedback_loop.aggregate_feedback(ontology_id=ontology_id)
        assert result is not None


class TestCrossModuleSimulationWorkflow:
    """跨模块端到端工作流：事件→推演→沙箱→反馈"""

    def test_full_simulation_pipeline(self, event_service, deduction_service, sandbox_service, feedback_loop):
        scenario = deduction_service.create_scenario(
            name="cross-module-e2e",
            description="Cross-module E2E test"
        )
        scenario_id = scenario["scenario_id"]

        deduction_service.load_ontology_conditions(scenario_id)

        chain = deduction_service.add_execution_chain(
            scenario_id=scenario_id,
            name="pipeline-chain",
            steps=[{
                "step_order": 1,
                "action_type_id": "deploy",
                "target_object_id": "unit-alpha",
                "target_object_type": "entity",
                "parameters": {"force": 500},
                "conditions": [],
                "description": "Deploy unit"
            }],
            conditions=[]
        )

        simulate = deduction_service.simulate_chain(scenario_id, chain["chain_id"])
        assert simulate["status"] == "success"

        sandbox = sandbox_service.create_sandbox(config={
            "max_memory_mb": 512,
            "max_time_seconds": 30,
            "workspace_id": "ws-cross-e2e"
        })
        sandbox_id = sandbox["sandbox_id"]

        sandbox_run = sandbox_service.run_simulation(
            sandbox_id=sandbox_id,
            params={
                "action_type_id": "deploy",
                "target_object_id": "unit-alpha",
                "target_object_type": "entity",
                "parameters": {"force": 500}
            }
        )
        assert sandbox_run["status"] == "success"

        feedback = feedback_loop.collect_feedback(
            source_id=scenario_id,
            feedback_type="action_result",
            outcome="success",
            data={"simulated": True, "sandbox_id": sandbox_id}
        )
        assert feedback is not None

        close = feedback_loop.close_loop(feedback)
        assert close["status"] == "success"

        sandbox_service.destroy_sandbox(sandbox_id)
        deduction_service.delete_scenario(scenario_id)
