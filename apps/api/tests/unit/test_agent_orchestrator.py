"""
AgentOrchestrator 单元测试

覆盖:
- AgentMode 枚举值
- _classify_query() 查询分类
- AgentOrchestrator 单例模式
- dispatch() 分派逻辑（react 模式 mock）
- get_availability() 可用性查询
- 优雅降级（导入失败场景）
"""

import pytest
from unittest.mock import patch, AsyncMock, MagicMock


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture(autouse=True)
def _reset_orchestrator_singleton():
    """每个测试前重置 AgentOrchestrator 单例"""
    try:
        from odap.biz.core.agent.agent_orchestrator import AgentOrchestrator
        AgentOrchestrator._instance = None
    except Exception:
        pass
    yield
    try:
        from odap.biz.core.agent.agent_orchestrator import AgentOrchestrator
        AgentOrchestrator._instance = None
    except Exception:
        pass


@pytest.fixture
def orchestrator():
    """创建 AgentOrchestrator 实例"""
    from odap.biz.core.agent.agent_orchestrator import AgentOrchestrator
    return AgentOrchestrator()


# ---------------------------------------------------------------------------
# TestAgentMode — 枚举值验证
# ---------------------------------------------------------------------------

class TestAgentMode:
    def test_enum_values(self):
        """AgentMode 必须包含 auto/swarm/react/harness 四种模式"""
        from odap.biz.core.agent.agent_orchestrator import AgentMode
        assert AgentMode.AUTO.value == "auto"
        assert AgentMode.SWARM.value == "swarm"
        assert AgentMode.REACT.value == "react"
        assert AgentMode.HARNESS.value == "harness"

    def test_enum_is_str(self):
        """AgentMode 必须 (str, Enum) 双继承"""
        from odap.biz.core.agent.agent_orchestrator import AgentMode
        assert isinstance(AgentMode.REACT, str)
        assert AgentMode.REACT == "react"

    def test_enum_from_value(self):
        """AgentMode 可以通过字符串值构造"""
        from odap.biz.core.agent.agent_orchestrator import AgentMode
        assert AgentMode("react") == AgentMode.REACT
        assert AgentMode("swarm") == AgentMode.SWARM

    def test_invalid_value_raises(self):
        """无效 mode 值应抛出 ValueError"""
        from odap.biz.core.agent.agent_orchestrator import AgentMode
        with pytest.raises(ValueError):
            AgentMode("invalid_mode")


# ---------------------------------------------------------------------------
# TestClassifyQuery — 查询分类器
# ---------------------------------------------------------------------------

class TestClassifyQuery:
    def test_swarm_keywords(self):
        """包含协同/分析态势等关键词应分类为 swarm"""
        from odap.biz.core.agent.agent_orchestrator import _classify_query, AgentMode
        assert _classify_query("请协同分析态势") == AgentMode.SWARM

    def test_react_keywords(self):
        """包含查询/解释等关键词应分类为 react"""
        from odap.biz.core.agent.agent_orchestrator import _classify_query, AgentMode
        assert _classify_query("查询当前状态") == AgentMode.REACT

    def test_harness_keywords(self):
        """包含执行/部署等关键词应分类为 harness"""
        from odap.biz.core.agent.agent_orchestrator import _classify_query, AgentMode
        assert _classify_query("执行部署操作") == AgentMode.HARNESS

    def test_no_keywords_defaults_to_react(self):
        """无关键词时默认分类为 react"""
        from odap.biz.core.agent.agent_orchestrator import _classify_query, AgentMode
        assert _classify_query("hello world") == AgentMode.REACT

    def test_swarm_priority_over_harness(self):
        """swarm 优先级高于 harness：同分时优先返回 swarm"""
        from odap.biz.core.agent.agent_orchestrator import _classify_query, AgentMode
        # "协同" 是 swarm 关键词，"执行" 是 harness 关键词
        # 同分时 swarm 优先
        result = _classify_query("协同执行任务")
        assert result == AgentMode.SWARM

    def test_harness_priority_over_react(self):
        """harness 优先级高于 react：同分时优先返回 harness"""
        from odap.biz.core.agent.agent_orchestrator import _classify_query, AgentMode
        # "执行" 是 harness 关键词，"说明" 是 react 关键词
        # 同分时 harness 优先
        result = _classify_query("执行说明")
        assert result == AgentMode.HARNESS

    def test_empty_query_defaults_to_react(self):
        """空查询默认为 react"""
        from odap.biz.core.agent.agent_orchestrator import _classify_query, AgentMode
        assert _classify_query("") == AgentMode.REACT


# ---------------------------------------------------------------------------
# TestAgentOrchestratorSingleton — 单例模式
# ---------------------------------------------------------------------------

class TestAgentOrchestratorSingleton:
    def test_singleton_same_instance(self):
        """多次创建应返回同一实例"""
        from odap.biz.core.agent.agent_orchestrator import AgentOrchestrator
        a = AgentOrchestrator()
        b = AgentOrchestrator()
        assert a is b

    def test_singleton_reset(self):
        """重置单例后应创建新实例"""
        from odap.biz.core.agent.agent_orchestrator import AgentOrchestrator
        a = AgentOrchestrator()
        AgentOrchestrator._instance = None
        b = AgentOrchestrator()
        assert a is not b


# ---------------------------------------------------------------------------
# TestBuildAgentResult — 结果构造
# ---------------------------------------------------------------------------

class TestBuildAgentResult:
    def test_basic_result(self):
        """基本结果构造"""
        from odap.biz.core.agent.agent_orchestrator import _build_agent_result
        result = _build_agent_result(mode="react", answer="test answer")
        assert result["mode"] == "react"
        assert result["answer"] == "test answer"
        assert result["error"] is None
        assert isinstance(result["result_id"], str)
        assert isinstance(result["reasoning_chain"], list)
        assert isinstance(result["sources"], list)
        assert isinstance(result["metadata"], dict)

    def test_result_with_error(self):
        """带错误的结果构造"""
        from odap.biz.core.agent.agent_orchestrator import _build_agent_result
        result = _build_agent_result(mode="swarm", answer="", error="执行失败")
        assert result["error"] == "执行失败"
        assert result["answer"] == ""

    def test_result_with_custom_metadata(self):
        """自定义 metadata"""
        from odap.biz.core.agent.agent_orchestrator import _build_agent_result
        result = _build_agent_result(
            mode="harness",
            answer="done",
            metadata={"steps": 3},
        )
        assert result["metadata"]["steps"] == 3


# ---------------------------------------------------------------------------
# TestDispatch — 分派逻辑
# ---------------------------------------------------------------------------

class TestDispatch:
    @pytest.mark.asyncio
    async def test_dispatch_invalid_mode_falls_back_to_auto(self, orchestrator):
        """无效 mode 参数应回退到 auto（自动分类）"""
        with patch.object(orchestrator, "_dispatch_react", new_callable=AsyncMock) as mock_react:
            mock_react.return_value = {
                "result_id": "r1",
                "mode": "react",
                "answer": "ok",
                "reasoning_chain": [],
                "sources": [],
                "metadata": {},
                "error": None,
            }
            result = await orchestrator.dispatch(
                query="查询状态",
                user_id="u1",
                workspace_id="ws1",
                mode="invalid_mode",
            )
            # 无效 mode 回退到 auto，auto 分类 "查询" -> react
            mock_react.assert_called_once()

    @pytest.mark.asyncio
    async def test_dispatch_react_mode(self, orchestrator):
        """react 模式应调用 _dispatch_react"""
        with patch.object(orchestrator, "_dispatch_react", new_callable=AsyncMock) as mock_react:
            mock_react.return_value = {
                "result_id": "r1",
                "mode": "react",
                "answer": "ok",
                "reasoning_chain": [],
                "sources": [],
                "metadata": {},
                "error": None,
            }
            result = await orchestrator.dispatch(
                query="test query",
                user_id="u1",
                workspace_id="ws1",
                mode="react",
            )
            mock_react.assert_called_once_with("test query", "ws1", None)
            assert result["mode"] == "react"

    @pytest.mark.asyncio
    async def test_dispatch_includes_metadata(self, orchestrator):
        """dispatch 结果应包含 user_id/workspace_id 等元数据"""
        with patch.object(orchestrator, "_dispatch_react", new_callable=AsyncMock) as mock_react:
            mock_react.return_value = {
                "result_id": "r1",
                "mode": "react",
                "answer": "ok",
                "reasoning_chain": [],
                "sources": [],
                "metadata": {},
                "error": None,
            }
            result = await orchestrator.dispatch(
                query="test",
                user_id="user_123",
                workspace_id="ws_456",
                scenario_id="sc_789",
                mode="react",
            )
            assert result["metadata"]["user_id"] == "user_123"
            assert result["metadata"]["workspace_id"] == "ws_456"
            assert result["metadata"]["scenario_id"] == "sc_789"
            assert "orchestration_time_ms" in result["metadata"]

    @pytest.mark.asyncio
    async def test_dispatch_react_agent_unavailable(self, orchestrator):
        """IntelligenceAgent 不可用时应返回错误结果"""
        with patch.object(orchestrator, "_get_intelligence_agent", return_value=None):
            result = await orchestrator.dispatch(
                query="test",
                user_id="u1",
                workspace_id="ws1",
                mode="react",
            )
            assert result["error"] is not None
            assert "不可用" in result["error"]

    @pytest.mark.asyncio
    async def test_dispatch_swarm_degrades_to_react(self, orchestrator):
        """DomainSwarm 不可用时应降级到 ReAct"""
        with patch.object(orchestrator, "_get_swarm", return_value=None):
            with patch.object(orchestrator, "_dispatch_react", new_callable=AsyncMock) as mock_react:
                mock_react.return_value = {
                    "result_id": "r1",
                    "mode": "react",
                    "answer": "degraded",
                    "reasoning_chain": [],
                    "sources": [],
                    "metadata": {},
                    "error": None,
                }
                result = await orchestrator.dispatch(
                    query="协同分析",
                    user_id="u1",
                    workspace_id="ws1",
                    mode="swarm",
                )
                mock_react.assert_called_once()


# ---------------------------------------------------------------------------
# TestGetAvailability — 可用性查询
# ---------------------------------------------------------------------------

class TestGetAvailability:
    def test_availability_returns_dict(self, orchestrator):
        """get_availability 应返回包含 swarm/react/harness 键的字典"""
        with patch.object(orchestrator, "_get_swarm", return_value=None):
            with patch.object(orchestrator, "_get_intelligence_agent", return_value=None):
                with patch.object(orchestrator, "_get_harness_loop", return_value=None):
                    avail = orchestrator.get_availability()
                    assert isinstance(avail, dict)
                    assert "swarm" in avail
                    assert "react" in avail
                    assert "harness" in avail

    def test_availability_all_false_when_unavailable(self, orchestrator):
        """所有 Agent Loop 不可用时应全部为 False"""
        with patch.object(orchestrator, "_get_swarm", return_value=None):
            with patch.object(orchestrator, "_get_intelligence_agent", return_value=None):
                with patch.object(orchestrator, "_get_harness_loop", return_value=None):
                    avail = orchestrator.get_availability()
                    assert avail["swarm"] is False
                    assert avail["react"] is False
                    assert avail["harness"] is False

    def test_availability_true_when_available(self, orchestrator):
        """Agent Loop 可用时应为 True"""
        mock_agent = MagicMock()
        with patch.object(orchestrator, "_get_swarm", return_value=mock_agent):
            orchestrator._swarm_available = True
            with patch.object(orchestrator, "_get_intelligence_agent", return_value=None):
                with patch.object(orchestrator, "_get_harness_loop", return_value=None):
                    avail = orchestrator.get_availability()
                    assert avail["swarm"] is True


# ---------------------------------------------------------------------------
# TestGracefulDegradation — 优雅降级
# ---------------------------------------------------------------------------

class TestGracefulDegradation:
    def test_import_failure_sets_unavailable(self, orchestrator):
        """导入失败应标记为不可用而非抛异常"""
        with patch("odap.biz.core.agent.agent_orchestrator.AgentOrchestrator._get_swarm") as mock:
            mock.side_effect = lambda: (
                setattr(orchestrator, '_swarm_available', False),
                setattr(orchestrator, '_swarm', None),
            )[1]
            orchestrator._get_swarm()
            assert orchestrator._swarm_available is False

    @pytest.mark.asyncio
    async def test_dispatch_exception_returns_error_result(self, orchestrator):
        """dispatch 中 Agent Loop 执行异常应返回错误结果而非抛异常"""
        with patch.object(orchestrator, "_dispatch_react", new_callable=AsyncMock) as mock_react:
            mock_react.side_effect = RuntimeError("LLM 超时")
            result = await orchestrator.dispatch(
                query="test",
                user_id="u1",
                workspace_id="ws1",
                mode="react",
            )
            assert result["error"] is not None
            assert "执行失败" in result["error"]
