import pytest
import sys
import os
import uuid
from unittest.mock import MagicMock, patch, AsyncMock
from datetime import datetime

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

OPENHARNESS_AVAILABLE = False
try:
    from openharness.tools.base import BaseTool
    OPENHARNESS_AVAILABLE = True
except ImportError:
    pass

skip_if_no_openharness = pytest.mark.skipif(
    not OPENHARNESS_AVAILABLE,
    reason="OpenHarness not available for integration testing",
)


class TestAgentDispatchAndRouting:
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
            mock_state.get_instance.return_value = MagicMock()
            mock_health.get_instance.return_value = MagicMock()
            from odap.biz.core.agent.swarm_orchestrator import DomainSwarm
            self.swarm = DomainSwarm()

    @pytest.mark.asyncio
    async def test_dispatch_intent_returns_task_id(self):
        result = await self.swarm.dispatch_intent(
            intent="分析A区威胁态势",
            context={"workspace_id": "ws-test"},
        )
        assert "task_id" in result
        assert "assigned_agent" in result
        assert result["status"] == "dispatched"

    @pytest.mark.asyncio
    async def test_dispatch_intent_routes_to_intelligence(self):
        result = await self.swarm.dispatch_intent(
            intent="查询敌方兵力部署",
            context={},
        )
        assert result["assigned_agent"] == "intelligence"

    @pytest.mark.asyncio
    async def test_dispatch_intent_routes_to_commander(self):
        result = await self.swarm.dispatch_intent(
            intent="制定作战方案",
            context={},
        )
        assert result["assigned_agent"] in ["commander", "intelligence"]

    @pytest.mark.asyncio
    async def test_dispatch_intent_with_workspace(self):
        result = await self.swarm.dispatch_intent(
            intent="态势分析",
            context={"workspace_id": "ws-001"},
            workspace_id="ws-001",
        )
        assert result["task_id"]
        assert "confidence" in result


class TestOODALoopExecution:
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
            mock_graph_instance = MagicMock()
            mock_graph_instance.add_entity = AsyncMock(return_value={"status": "ok"})
            mock_graph_instance.search_entities = MagicMock(return_value=[])
            mock_graph.return_value = mock_graph_instance
            mock_fault.get_instance.return_value = MagicMock()
            mock_state_inst = MagicMock()
            mock_state_inst.save_checkpoint = AsyncMock()
            mock_state.get_instance.return_value = mock_state_inst
            mock_health.get_instance.return_value = MagicMock()
            from odap.biz.core.agent.swarm_orchestrator import DomainSwarm
            self.swarm = DomainSwarm()

    @pytest.mark.asyncio
    async def test_ooda_observe_phase(self):
        intel_agent = self.swarm.agents[
            __import__("odap.biz.core.agent.agent_factory", fromlist=["AgentType"]).AgentType.INTELLIGENCE
        ]
        intel_agent.gather_intelligence = AsyncMock(return_value={
            "observations": [{"type": "threat", "location": "Sector-5"}],
            "confidence": 0.85,
        })
        result = await self.swarm._observe("检测Sector-5威胁", None)
        assert "observations" in result
        assert result["confidence"] == 0.85

    @pytest.mark.asyncio
    async def test_ooda_orient_phase(self):
        observe_result = {
            "observations": [{"type": "threat", "location": "Sector-5"}],
            "confidence": 0.85,
        }
        intel_agent = self.swarm.agents[
            __import__("odap.biz.core.agent.agent_factory", fromlist=["AgentType"]).AgentType.INTELLIGENCE
        ]
        intel_agent.analyze_situation = AsyncMock(return_value={
            "analysis": "威胁等级高",
            "threats": [{"id": "t1", "level": "high"}],
            "recommendations": ["增援Sector-5"],
        })
        result = await self.swarm._orient(observe_result, None)
        assert "analysis" in result

    @pytest.mark.asyncio
    async def test_ooda_decide_phase(self):
        orient_result = {
            "analysis": "威胁等级高",
            "threats": [{"id": "t1", "level": "high"}],
            "recommendations": ["增援Sector-5"],
        }
        commander = self.swarm.agents[
            __import__("odap.biz.core.agent.agent_factory", fromlist=["AgentType"]).AgentType.COMMANDER
        ]
        commander.analyze_situation = AsyncMock(return_value={
            "decision": "deploy_reinforcement",
            "targets": ["Sector-5"],
            "requires_confirmation": False,
        })
        result = await self.swarm._decide(orient_result, None)
        assert "decision" in result

    @pytest.mark.asyncio
    async def test_ooda_act_phase(self):
        decide_result = {
            "decision": "deploy_reinforcement",
            "targets": ["Sector-5"],
            "requires_confirmation": False,
        }
        operations = self.swarm.agents[
            __import__("odap.biz.core.agent.agent_factory", fromlist=["AgentType"]).AgentType.OPERATIONS
        ]
        operations.execute_order = AsyncMock(return_value={
            "status": "completed",
            "order_type": "deploy_reinforcement",
            "results": [{"target": "Sector-5", "success": True}],
        })
        result = await self.swarm._act(decide_result, None)
        assert result["status"] == "completed"

    @pytest.mark.asyncio
    async def test_decision_chain_retrieval(self):
        from odap.biz.core.agent.swarm_orchestrator import MissionResult, OODAPhase
        mock_result = MissionResult(
            mission_id="test-mission-001",
            success=True,
            phases_completed=[OODAPhase.OBSERVE, OODAPhase.ORIENT, OODAPhase.DECIDE, OODAPhase.ACT],
            final_decision={"decision": "deploy"},
            execution_time_ms=1500.0,
        )
        self.swarm.mission_history.append(mock_result)
        chain = await self.swarm.get_decision_chain("test-mission-001")
        assert chain["task_id"] == "test-mission-001"
        assert len(chain["chain"]) == 4
        assert chain["final_decision"]["decision"] == "deploy"


@skip_if_no_openharness
class TestOpenHarnessAdapterIntegration:
    def test_engine_adapter_import(self):
        from odap.infra.openharness.engine_adapter import OPENHARNESS_AVAILABLE
        assert OPENHARNESS_AVAILABLE is True

    def test_tool_adapter_import(self):
        from odap.infra.openharness.tool_adapter import ToolAdapterV2
        adapter = ToolAdapterV2()
        assert adapter is not None
