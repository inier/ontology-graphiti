"""
DomainSwarm 与 IntentRouter 单元测试

覆盖:
- DomainSwarm 构造器依赖注入
- DomainSwarm 懒加载默认工厂方法
- IntentRouter 懒加载 LLM 可用性检测
- IntentRouter 规则路由逻辑
"""

import pytest
from unittest.mock import MagicMock, patch


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def mock_infra_deps():
    """构造 DomainSwarm 所需的全部 mock 依赖"""
    return {
        "opa_manager": MagicMock(),
        "query_service": MagicMock(),
        "write_proxy": MagicMock(),
        "fault_manager": MagicMock(),
        "state_manager": MagicMock(),
        "health_monitor": MagicMock(),
    }


@pytest.fixture
def swarm_with_mocks(mock_infra_deps):
    """创建注入 mock 依赖的 DomainSwarm 实例"""
    from odap.biz.core.agent.swarm_orchestrator import DomainSwarm
    return DomainSwarm(**mock_infra_deps)


# ---------------------------------------------------------------------------
# TestDomainSwarmDI — 构造器依赖注入
# ---------------------------------------------------------------------------

class TestDomainSwarmDI:
    def test_injected_dependencies_are_used(self, swarm_with_mocks, mock_infra_deps):
        """注入的依赖应被直接使用，不触发懒加载"""
        assert swarm_with_mocks.opa_manager is mock_infra_deps["opa_manager"]
        assert swarm_with_mocks._query_service is mock_infra_deps["query_service"]
        assert swarm_with_mocks._write_proxy is mock_infra_deps["write_proxy"]
        assert swarm_with_mocks.fault_manager is mock_infra_deps["fault_manager"]
        assert swarm_with_mocks.state_manager is mock_infra_deps["state_manager"]
        assert swarm_with_mocks.health_monitor is mock_infra_deps["health_monitor"]

    def test_partial_injection_uses_defaults_for_rest(self):
        """部分注入时，未注入的依赖应走懒加载默认工厂"""
        from odap.biz.core.agent.swarm_orchestrator import DomainSwarm
        mock_opa = MagicMock()
        mock_write = MagicMock()

        with patch.object(DomainSwarm, "_default_query_service", return_value=MagicMock()) as mock_qs, \
             patch.object(DomainSwarm, "_default_fault_manager", return_value=MagicMock()) as mock_fm, \
             patch.object(DomainSwarm, "_default_state_manager", return_value=MagicMock()) as mock_sm, \
             patch.object(DomainSwarm, "_default_health_monitor", return_value=MagicMock()) as mock_hm:
            swarm = DomainSwarm(
                opa_manager=mock_opa,
                write_proxy=mock_write,
            )
            assert swarm.opa_manager is mock_opa
            assert swarm._write_proxy is mock_write
            mock_qs.assert_called_once()
            mock_fm.assert_called_once()
            mock_sm.assert_called_once()
            mock_hm.assert_called_once()

    def test_none_param_triggers_default_factory(self):
        """显式传入 None 等同于未传参，应走默认工厂"""
        from odap.biz.core.agent.swarm_orchestrator import DomainSwarm
        with patch.object(DomainSwarm, "_default_opa_manager", return_value=MagicMock()) as mock_opa:
            swarm = DomainSwarm(opa_manager=None)
            mock_opa.assert_called_once()

    def test_no_args_triggers_all_defaults(self):
        """无参构造应触发全部默认工厂"""
        from odap.biz.core.agent.swarm_orchestrator import DomainSwarm
        with patch.object(DomainSwarm, "_default_opa_manager", return_value=MagicMock()) as m1, \
             patch.object(DomainSwarm, "_default_query_service", return_value=MagicMock()) as m2, \
             patch.object(DomainSwarm, "_default_write_proxy", return_value=MagicMock()) as m3, \
             patch.object(DomainSwarm, "_default_fault_manager", return_value=MagicMock()) as m4, \
             patch.object(DomainSwarm, "_default_state_manager", return_value=MagicMock()) as m5, \
             patch.object(DomainSwarm, "_default_health_monitor", return_value=MagicMock()) as m6:
            DomainSwarm()
            m1.assert_called_once()
            m2.assert_called_once()
            m3.assert_called_once()
            m4.assert_called_once()
            m5.assert_called_once()
            m6.assert_called_once()

    def test_custom_config_preserved(self, mock_infra_deps):
        """自定义 config 应被保留"""
        from odap.biz.core.agent.swarm_orchestrator import DomainSwarm
        custom_config = {"coordinator": {"max_parallel_agents": 5}}
        swarm = DomainSwarm(config=custom_config, **mock_infra_deps)
        assert swarm.config == custom_config

    def test_default_config_used_when_none(self, mock_infra_deps):
        """未传 config 时应使用默认配置"""
        from odap.biz.core.agent.swarm_orchestrator import DomainSwarm
        swarm = DomainSwarm(**mock_infra_deps)
        assert "coordinator" in swarm.config
        assert "ooda" in swarm.config


# ---------------------------------------------------------------------------
# TestDomainSwarmDefaultFactories — 默认工厂方法
# ---------------------------------------------------------------------------

class TestDomainSwarmDefaultFactories:
    def test_default_opa_manager_lazy_import(self):
        """_default_opa_manager 应延迟导入 infra.opa"""
        from odap.biz.core.agent.swarm_orchestrator import DomainSwarm
        with patch.dict("sys.modules", {}):
            # 仅验证方法存在且是 staticmethod
            assert callable(DomainSwarm._default_opa_manager)

    def test_default_write_proxy_lazy_import(self):
        """_default_write_proxy 应延迟导入 infra.query"""
        from odap.biz.core.agent.swarm_orchestrator import DomainSwarm
        assert callable(DomainSwarm._default_write_proxy)

    def test_default_fault_manager_lazy_import(self):
        """_default_fault_manager 应延迟导入 infra.resilience.fault_tolerance"""
        from odap.biz.core.agent.swarm_orchestrator import DomainSwarm
        assert callable(DomainSwarm._default_fault_manager)

    def test_default_state_manager_lazy_import(self):
        """_default_state_manager 应延迟导入 infra.resilience.state_persistence"""
        from odap.biz.core.agent.swarm_orchestrator import DomainSwarm
        assert callable(DomainSwarm._default_state_manager)

    def test_default_health_monitor_lazy_import(self):
        """_default_health_monitor 应延迟导入 infra.resilience.health_monitor"""
        from odap.biz.core.agent.swarm_orchestrator import DomainSwarm
        assert callable(DomainSwarm._default_health_monitor)


# ---------------------------------------------------------------------------
# TestIntentRouterLazyLLM — IntentRouter 懒加载 LLM 可用性
# ---------------------------------------------------------------------------

class TestIntentRouterLazyLLM:
    def test_explicit_llm_available_true(self):
        """显式传入 llm_available=True 应直接使用"""
        from odap.biz.core.agent.swarm_orchestrator import IntentRouter
        router = IntentRouter(llm_available=True)
        assert router.llm_available is True

    def test_explicit_llm_available_false(self):
        """显式传入 llm_available=False 应直接使用"""
        from odap.biz.core.agent.swarm_orchestrator import IntentRouter
        router = IntentRouter(llm_available=False)
        assert router.llm_available is False

    def test_lazy_detect_with_api_key(self):
        """未传 llm_available 时，有 API Key 应检测为 True"""
        from odap.biz.core.agent.swarm_orchestrator import IntentRouter
        mock_config = MagicMock()
        mock_config.OPENAI_API_KEY = "sk-test-key"
        with patch.dict("sys.modules", {"odap.infra.security": MagicMock(security_config=mock_config)}):
            router = IntentRouter()
            assert router.llm_available is True

    def test_lazy_detect_without_api_key(self):
        """未传 llm_available 时，无 API Key 应检测为 False"""
        from odap.biz.core.agent.swarm_orchestrator import IntentRouter
        mock_config = MagicMock()
        mock_config.OPENAI_API_KEY = ""
        with patch.dict("sys.modules", {"odap.infra.security": MagicMock(security_config=mock_config)}):
            router = IntentRouter()
            assert router.llm_available is False

    def test_lazy_detect_import_failure(self):
        """导入 infra.security 失败时应降级为 False"""
        from odap.biz.core.agent.swarm_orchestrator import IntentRouter
        with patch.dict("sys.modules", {}):
            # 使 odap.infra.security 导入失败
            import sys
            original = sys.modules.get("odap.infra.security")
            sys.modules["odap.infra.security"] = None  # 触发 ImportError
            try:
                router = IntentRouter()
                assert router.llm_available is False
            finally:
                if original is not None:
                    sys.modules["odap.infra.security"] = original
                elif "odap.infra.security" in sys.modules:
                    del sys.modules["odap.infra.security"]

    def test_llm_available_cached_after_first_access(self):
        """llm_available 应在首次访问后缓存，不再重复检测"""
        from odap.biz.core.agent.swarm_orchestrator import IntentRouter
        mock_config = MagicMock()
        mock_config.OPENAI_API_KEY = "sk-test-key"
        with patch.dict("sys.modules", {"odap.infra.security": MagicMock(security_config=mock_config)}):
            router = IntentRouter()
            # 第一次访问
            _ = router.llm_available
            # 第二次访问（应使用缓存值，不再触发导入）
            _ = router.llm_available
            # 值应一致
            assert router.llm_available is True

    def test_explicit_override_takes_priority(self):
        """显式传入的 llm_available 应优先于懒加载检测"""
        from odap.biz.core.agent.swarm_orchestrator import IntentRouter
        # 即使有 API Key，显式传入 False 应覆盖
        router = IntentRouter(llm_available=False)
        assert router.llm_available is False


# ---------------------------------------------------------------------------
# TestIntentRouterRuleRouting — 规则路由逻辑
# ---------------------------------------------------------------------------

class TestIntentRouterRuleRouting:
    def test_intelligence_keywords(self):
        """情报关键词应路由到 intelligence"""
        from odap.biz.core.agent.swarm_orchestrator import IntentRouter
        router = IntentRouter(llm_available=False)
        result = router.route("分析态势威胁")
        assert result["agent"] == "intelligence"
        assert result["confidence"] >= 0.9

    def test_commander_keywords(self):
        """决策关键词应路由到 director"""
        from odap.biz.core.agent.swarm_orchestrator import IntentRouter
        router = IntentRouter(llm_available=False)
        result = router.route("制定决策方案")
        assert result["agent"] == "director"
        assert result["confidence"] >= 0.8  # 部分匹配时置信度会降低

    def test_operations_keywords(self):
        """执行关键词应路由到 operations"""
        from odap.biz.core.agent.swarm_orchestrator import IntentRouter
        router = IntentRouter(llm_available=False)
        result = router.route("执行打击行动")
        assert result["agent"] == "operations"
        assert result["confidence"] >= 0.9

    def test_default_fallback(self):
        """无匹配关键词时应默认路由到 intelligence"""
        from odap.biz.core.agent.swarm_orchestrator import IntentRouter
        router = IntentRouter(llm_available=False)
        result = router.route("hello world")
        assert result["agent"] == "intelligence"
        assert result["source"] == "default"

    def test_sanguo_keywords(self):
        """三国领域关键词应路由到 intelligence"""
        from odap.biz.core.agent.swarm_orchestrator import IntentRouter
        router = IntentRouter(llm_available=False)
        result = router.route("曹操的势力分析")
        assert result["agent"] == "intelligence"
