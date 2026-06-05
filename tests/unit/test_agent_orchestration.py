"""
Agent 编排单元测试 - 对齐 odap/biz/core/agent/

覆盖:
- swarm_orchestrator: IntentRouter 路由、SubAgentPlanner 规划、OODAProgress/MissionResult 数据模型
- orchestrator: SelfCorrectingOrchestrator 查询解析与路由
- decision_service: DecisionService 创建决策、记录步骤、获取决策链
"""

import pytest
from unittest.mock import MagicMock, patch, AsyncMock
from datetime import datetime


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def intent_router():
    """创建 IntentRouter 实例"""
    from odap.biz.core.agent.swarm_orchestrator import IntentRouter
    return IntentRouter()


@pytest.fixture
def sub_agent_planner():
    """创建 SubAgentPlanner 实例"""
    from odap.biz.core.agent.swarm_orchestrator import SubAgentPlanner
    return SubAgentPlanner()


@pytest.fixture
def decision_service():
    """创建独立的 DecisionService 实例（重置单例）"""
    from odap.biz.core.agent.services.decision_service import DecisionService
    DecisionService._instance = None
    svc = DecisionService()
    return svc


@pytest.fixture
def orchestrator():
    """创建 SelfCorrectingOrchestrator 实例"""
    from odap.biz.core.agent.orchestrator import SelfCorrectingOrchestrator
    with patch("odap.biz.core.agent.orchestrator.OPAManager"):
        orch = SelfCorrectingOrchestrator(user_role="commander")
    # 确保 SKILL_CATALOG 为空，使技能查找返回不存在
    patcher = patch("odap.biz.core.agent.orchestrator.SKILL_CATALOG", {})
    patcher.start()
    return orch


# ===========================================================================
# TestIntentRouter - 意图路由
# ===========================================================================

class TestIntentRouter:
    """IntentRouter 意图路由测试"""

    def test_route_intelligence_keyword(self, intent_router):
        """包含情报关键词应路由到 intelligence agent"""
        result = intent_router.route("分析当前态势威胁")
        assert result["agent"] == "intelligence"
        assert result["confidence"] > 0

    def test_route_commander_keyword(self, intent_router):
        """包含决策关键词应路由到 commander agent"""
        result = intent_router.route("制定决策方案")
        assert result["agent"] == "commander"

    def test_route_operations_keyword(self, intent_router):
        """包含执行关键词应路由到 operations agent"""
        result = intent_router.route("执行打击行动")
        assert result["agent"] == "operations"

    def test_route_default_fallback(self, intent_router):
        """无法识别的意图应默认路由到 intelligence"""
        # 禁用 LLM 路由，确保走规则默认回退
        intent_router._llm_available = False
        result = intent_router.route("hello world xyz")
        assert result["agent"] == "intelligence"
        assert result["confidence"] == 0.5
        assert result["source"] == "default"

    def test_route_returns_source_field(self, intent_router):
        """路由结果应包含 source 字段"""
        result = intent_router.route("搜索雷达信息")
        assert "source" in result
        assert result["source"] in ("rule", "llm", "default")


# ===========================================================================
# TestSubAgentPlanner - 子 Agent 规划
# ===========================================================================

class TestSubAgentPlanner:
    """SubAgentPlanner 子 Agent 规划测试"""

    def test_plan_for_intelligence_agent(self, sub_agent_planner):
        """intelligence agent 应规划情报收集和分析任务"""
        tasks = sub_agent_planner.plan("分析态势", "intelligence")
        assert len(tasks) >= 1
        task_actions = [t["action"] for t in tasks]
        assert "gather_intelligence" in task_actions

    def test_plan_for_commander_agent(self, sub_agent_planner):
        """commander agent 应规划情报收集、态势分析和决策任务"""
        tasks = sub_agent_planner.plan("制定决策", "commander")
        assert len(tasks) >= 2
        task_actions = [t["action"] for t in tasks]
        assert "analyze_situation" in task_actions
        assert "make_decision" in task_actions

    def test_plan_for_operations_agent(self, sub_agent_planner):
        """operations agent 应规划完整的 OODA 链路"""
        tasks = sub_agent_planner.plan("执行行动", "operations")
        assert len(tasks) >= 3
        task_sub_agents = [t["sub_agent"] for t in tasks]
        assert "intelligence" in task_sub_agents
        assert "commander" in task_sub_agents
        assert "operations" in task_sub_agents


# ===========================================================================
# TestOODADataModels - OODA 数据模型
# ===========================================================================

class TestOODADataModels:
    """OODA 数据模型测试"""

    def test_ooda_progress_to_dict(self):
        """OODAProgress.to_dict 应返回完整字典"""
        from odap.biz.core.agent.swarm_orchestrator import OODAProgress, OODAPhase, OODAStatus
        from odap.biz.core.agent.agent_factory import AgentType

        progress = OODAProgress(
            phase=OODAPhase.OBSERVE,
            status=OODAStatus.COMPLETED,
            agent=AgentType.INTELLIGENCE,
            message="感知完成",
            data={"summary": "测试"},
        )
        d = progress.to_dict()
        assert d["phase"] == "observe"
        assert d["status"] == "completed"
        assert d["agent"] == "intelligence"
        assert d["message"] == "感知完成"
        assert d["data"] == {"summary": "测试"}

    def test_mission_result_to_dict(self):
        """MissionResult.to_dict 应返回完整字典"""
        from odap.biz.core.agent.swarm_orchestrator import MissionResult, OODAPhase

        result = MissionResult(
            mission_id="mission-001",
            success=True,
            phases_completed=[OODAPhase.OBSERVE, OODAPhase.DECIDE],
            final_decision={"action": "observe"},
            execution_time_ms=123.45,
            graphiti_episodes=["ep-1"],
        )
        d = result.to_dict()
        assert d["mission_id"] == "mission-001"
        assert d["success"] is True
        assert d["phases_completed"] == ["observe", "decide"]
        assert d["execution_time_ms"] == 123.45


# ===========================================================================
# TestSelfCorrectingOrchestrator - 自校正编排器
# ===========================================================================

class TestSelfCorrectingOrchestrator:
    """SelfCorrectingOrchestrator 编排器测试"""

    def test_parse_radar_query(self, orchestrator):
        """解析雷达查询应返回 search_radar 技能"""
        skill_name, args = orchestrator._parse_query("帮我看看 B 区有没有雷达")
        assert skill_name == "search_radar"
        assert args["area"] == "B"

    def test_parse_domain_analysis_query(self, orchestrator):
        """解析领域分析查询应返回 analyze_domain 技能"""
        skill_name, args = orchestrator._parse_query("分析领域态势")
        assert skill_name == "analyze_domain"

    def test_parse_strike_recommendation_query(self, orchestrator):
        """解析打击推荐查询应返回 recommend_strike_targets 技能"""
        skill_name, args = orchestrator._parse_query("推荐 A 区打击目标")
        assert skill_name == "recommend_strike_targets"
        assert args["area"] == "A"

    def test_parse_force_comparison_query(self, orchestrator):
        """解析力量对比查询应返回 analyze_force_comparison 技能"""
        skill_name, args = orchestrator._parse_query("对比 C 区力量")
        assert skill_name == "analyze_force_comparison"
        assert args["area"] == "C"

    def test_parse_attack_query(self, orchestrator):
        """解析攻击查询应返回 attack_target 技能"""
        skill_name, args = orchestrator._parse_query("攻击 TARGET_001")
        assert skill_name == "attack_target"
        assert args["target_id"] is not None

    def test_run_with_nonexistent_skill_returns_error(self, orchestrator):
        """执行不存在的技能应返回错误"""
        result = orchestrator.run("帮我看看 B 区有没有雷达")
        assert result["status"] == "error"
        assert "技能不存在" in result["message"]


# ===========================================================================
# TestDecisionService - 决策服务
# ===========================================================================

class TestDecisionService:
    """DecisionService 决策服务测试"""

    def test_create_decision(self, decision_service):
        """创建决策应返回 decision_id"""
        result = decision_service.create_decision(
            task_id="task-001",
            workspace_id="ws-001",
            reasoning="测试决策",
        )
        assert "decision_id" in result
        assert result["task_id"] == "task-001"
        assert result["workspace_id"] == "ws-001"

    def test_record_step(self, decision_service):
        """记录决策步骤应返回步骤信息"""
        create_result = decision_service.create_decision(task_id="task-001")
        decision_id = create_result["decision_id"]

        from odap.biz.core.agent.models.decision_chain import DecisionPhase
        step_result = decision_service.record_step(
            decision_id=decision_id,
            phase=DecisionPhase.OBSERVE,
            description="感知阶段完成",
            evidence=[{"source": "radar", "data": "敌情信息"}],
        )
        assert step_result["decision_id"] == decision_id
        assert step_result["phase"] == "observe"
        assert step_result["description"] == "感知阶段完成"

    def test_get_decision_chain(self, decision_service):
        """获取决策链应返回所有步骤"""
        from odap.biz.core.agent.models.decision_chain import DecisionPhase

        create_result = decision_service.create_decision(task_id="task-001")
        decision_id = create_result["decision_id"]

        decision_service.record_step(decision_id, DecisionPhase.OBSERVE, "感知")
        decision_service.record_step(decision_id, DecisionPhase.DECIDE, "决策")

        chain = decision_service.get_decision_chain(decision_id)
        assert "steps" in chain
        assert len(chain["steps"]) == 2
        assert chain["steps"][0]["phase"] == "observe"
        assert chain["steps"][1]["phase"] == "decide"

    def test_get_nonexistent_decision_returns_error(self, decision_service):
        """获取不存在的决策应返回错误"""
        result = decision_service.get_decision("nonexistent-id")
        assert result["status"] == "error"

    def test_list_decisions(self, decision_service):
        """列出决策应返回分页结果"""
        decision_service.create_decision(task_id="task-001", workspace_id="ws-001")
        decision_service.create_decision(task_id="task-002", workspace_id="ws-001")
        decision_service.create_decision(task_id="task-003", workspace_id="ws-002")

        result = decision_service.list_decisions(workspace_id="ws-001")
        assert result["total"] == 2

        all_result = decision_service.list_decisions()
        assert all_result["total"] == 3

    def test_record_step_creates_decision_automatically(self, decision_service):
        """record_step 对不存在的 decision_id 应自动创建决策链"""
        from odap.biz.core.agent.models.decision_chain import DecisionPhase

        result = decision_service.record_step(
            decision_id="auto-created-id",
            phase=DecisionPhase.ACT,
            description="自动创建",
        )
        assert result["decision_id"] == "auto-created-id"

        # 验证决策链已创建
        chain = decision_service.get_decision_chain("auto-created-id")
        assert len(chain["steps"]) == 1
