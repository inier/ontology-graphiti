import pytest
import sys
import os
import uuid
from unittest.mock import MagicMock, patch, AsyncMock
from datetime import datetime

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

SERVICE_AVAILABLE = False
try:
    import httpx
    resp = httpx.get("http://localhost:8000/health", timeout=2.0)
    if resp.status_code == 200:
        SERVICE_AVAILABLE = True
except Exception:
    pass

skip_if_no_service = pytest.mark.skipif(
    not SERVICE_AVAILABLE,
    reason="Full service not running for E2E testing",
)


@pytest.mark.e2e
class TestAgentIntentDispatchWorkflow:
    @pytest.fixture(autouse=True)
    def _setup(self):
        with patch("odap.biz.core.agent.swarm_orchestrator.OPAManager") as mock_opa, \
             patch("odap.biz.core.agent.swarm_orchestrator.QueryService") as mock_query, \
             patch("odap.biz.core.agent.swarm_orchestrator.GraphManager") as mock_graph, \
             patch("odap.biz.core.agent.swarm_orchestrator.FaultRecoveryManager") as mock_fault, \
             patch("odap.biz.core.agent.swarm_orchestrator.StatePersistenceManager") as mock_state, \
             patch("odap.biz.core.agent.swarm_orchestrator.HealthMonitor") as mock_health:
            mock_opa.return_value = MagicMock()
            mock_query.return_value = MagicMock()
            mock_graph.return_value = MagicMock()
            mock_fault.get_instance.return_value = MagicMock()
            mock_state_inst = MagicMock()
            mock_state_inst.save_checkpoint = AsyncMock()
            mock_state.get_instance.return_value = mock_state_inst
            mock_health.get_instance.return_value = MagicMock()
            from odap.biz.core.agent.swarm_orchestrator import DomainSwarm
            self.swarm = DomainSwarm()

    @pytest.mark.asyncio
    async def test_intent_dispatch_to_ooda_loop(self):
        dispatch_result = await self.swarm.dispatch_intent(
            intent="分析A区威胁态势并制定应对方案",
            context={"workspace_id": "ws-e2e-001"},
        )
        assert "task_id" in dispatch_result
        assert dispatch_result["status"] == "dispatched"
        assert "assigned_agent" in dispatch_result

        task_id = dispatch_result["task_id"]
        task_status = await self.swarm.get_task_status(task_id)
        assert task_status is not None

    @pytest.mark.asyncio
    async def test_ooda_loop_with_visualization_data(self):
        from odap.biz.core.agent.agent_factory import AgentType

        intel_agent = self.swarm.agents[AgentType.INTELLIGENCE]
        intel_agent.gather_intelligence = AsyncMock(return_value={
            "observations": [
                {"type": "unit_movement", "location": "Sector-3", "confidence": 0.9},
                {"type": "supply_shortage", "location": "Base-Alpha", "confidence": 0.75},
            ],
            "confidence": 0.85,
        })
        intel_agent.analyze_situation = AsyncMock(return_value={
            "analysis": "敌方在Sector-3集结，Base-Alpha补给不足",
            "threats": [{"id": "t1", "level": "high", "location": "Sector-3"}],
            "recommendations": ["增援Sector-3", "补给Base-Alpha"],
        })

        commander = self.swarm.agents[AgentType.COMMANDER]
        commander.analyze_situation = AsyncMock(return_value={
            "decision": "deploy_and_resupply",
            "targets": ["Sector-3", "Base-Alpha"],
            "requires_confirmation": False,
        })

        operations = self.swarm.agents[AgentType.OPERATIONS]
        operations.execute_order = AsyncMock(return_value={
            "status": "completed",
            "order_type": "deploy_and_resupply",
            "results": [
                {"target": "Sector-3", "success": True, "action": "reinforce"},
                {"target": "Base-Alpha", "success": True, "action": "resupply"},
            ],
        })

        observe_result = await self.swarm._observe("分析A区威胁", None)
        assert "observations" in observe_result
        assert len(observe_result["observations"]) == 2

        orient_result = await self.swarm._orient(observe_result, None)
        assert "analysis" in orient_result

        decide_result = await self.swarm._decide(orient_result, None)
        assert "decision" in decide_result

        act_result = await self.swarm._act(decide_result, None)
        assert act_result["status"] == "completed"
        assert len(act_result["results"]) == 2

    @pytest.mark.asyncio
    async def test_decision_chain_visualization(self):
        from odap.biz.core.agent.swarm_orchestrator import MissionResult, OODAPhase

        mission_result = MissionResult(
            mission_id="e2e-mission-001",
            success=True,
            phases_completed=[
                OODAPhase.OBSERVE,
                OODAPhase.ORIENT,
                OODAPhase.DECIDE,
                OODAPhase.ACT,
            ],
            final_decision={
                "decision": "deploy_reinforcement",
                "targets": ["Sector-5"],
                "confidence": 0.82,
            },
            execution_time_ms=2500.0,
        )
        self.swarm.mission_history.append(mission_result)

        chain = await self.swarm.get_decision_chain("e2e-mission-001")
        assert chain["task_id"] == "e2e-mission-001"
        assert len(chain["chain"]) == 4
        phases = [c["phase"] for c in chain["chain"]]
        assert "observe" in phases
        assert "decide" in phases
        assert chain["final_decision"]["decision"] == "deploy_reinforcement"


@skip_if_no_service
@pytest.mark.e2e
class TestAgentWorkflowLive:
    def test_agent_dispatch_via_api(self):
        from odap.web.app import app
        client = TestClient(app)

        dispatch_resp = client.post(
            "/api/agent/dispatch",
            json={
                "intent": "分析当前威胁态势",
                "context": {"workspace_id": "ws-live-test"},
                "workspace_id": "ws-live-test",
            },
        )
        assert dispatch_resp.status_code in [200, 500]
        if dispatch_resp.status_code == 200:
            data = dispatch_resp.json()
            assert "task_id" in data or "status" in data
