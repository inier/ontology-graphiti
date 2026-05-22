import pytest
from unittest.mock import Mock, patch, MagicMock, AsyncMock
from dataclasses import dataclass


@dataclass
class FakeSkillHealthInfo:
    name: str
    status: str
    health: str
    registered_at: str = ""
    last_modified: str = ""
    total_calls: int = 0
    success_calls: int = 0
    failed_calls: int = 0
    avg_execution_time_ms: float = 0
    last_execution_time: str = None
    last_error: str = None


class _EnumLike:
    def __init__(self, value):
        self.value = value
    def __eq__(self, other):
        if isinstance(other, _EnumLike):
            return self.value == other.value
        return self.value == other
    def __repr__(self):
        return f"HealthStatus.{self.value.upper()}"


class FakeHealthStatus:
    HEALTHY = _EnumLike("healthy")
    DEGRADED = _EnumLike("degraded")
    UNHEALTHY = _EnumLike("unhealthy")


class FakeSkillMetadata:
    def __init__(self, name="test", description="", category="test",
                 danger_level="low", opa_action="", requires_opa_check=False):
        self.name = name
        self.description = description
        self.category = category
        self.danger_level = danger_level
        self.opa_action = opa_action
        self.requires_opa_check = requires_opa_check


class FakeBaseSkill:
    def __init__(self, name="test_skill", description="test", category="test"):
        self.metadata = FakeSkillMetadata(name=name, description=description, category=category)
        self.input_schema = None


class FakeSkillRegistryV2:
    def __init__(self):
        self._skills = {}

    def register(self, skill, version="1.0.0", changelog=""):
        self._skills[skill.metadata.name] = skill
        return True

    def get_executor(self):
        return self


class FakeSkillExecutorV2:
    def execute(self, skill_name, input_data):
        return Mock(success=True, data={"result": "ok"}, error=None)


@pytest.fixture
def mock_base_v2():
    fake_registry = FakeSkillRegistryV2()
    fake_executor = FakeSkillExecutorV2()
    with patch.dict("sys.modules", {
        "tools": MagicMock(),
        "tools.base_v2": MagicMock(
            SkillRegistryV2=FakeSkillRegistryV2,
            SkillExecutorV2=FakeSkillExecutorV2,
            get_registry_v2=lambda: fake_registry,
            SkillStatus=MagicMock(REGISTERED="registered", ACTIVE="active"),
            HealthStatus=FakeHealthStatus,
            SkillHealthInfo=FakeSkillHealthInfo,
            BaseSkill=FakeBaseSkill,
            SkillInput=MagicMock,
            SkillOutput=MagicMock,
            SkillMetadata=FakeSkillMetadata,
        ),
    }):
        yield fake_registry


@pytest.fixture
def registry(mock_base_v2):
    from odap.biz.tool_registry.registry import ToolRegistry
    return ToolRegistry()


class TestToolType:
    def test_tool_type_values(self, mock_base_v2):
        from odap.biz.tool_registry.registry import ToolType
        assert ToolType.SKILL.value == "skill"
        assert ToolType.MCP.value == "mcp"
        assert ToolType.REST.value == "rest"
        assert ToolType.FUNCTION.value == "function"


class TestToolMetadata:
    def test_tool_metadata_defaults(self, mock_base_v2):
        from odap.biz.tool_registry.registry import ToolMetadata
        meta = ToolMetadata(
            name="test_tool",
            description="A test tool",
            tool_type="function",
            category="test",
        )
        assert meta.name == "test_tool"
        assert meta.version == "1.0.0"
        assert meta.danger_level == "low"
        assert meta.capabilities == []
        assert meta.semantic_tags == []
        assert meta.requires_opa_check is False
        assert meta.rate_limit == 100
        assert meta.timeout_ms == 30000


class TestToolRegistration:
    def test_tool_registration_post_init(self, mock_base_v2):
        from odap.biz.tool_registry.registry import ToolRegistration, ToolMetadata, ToolType
        meta = ToolMetadata(name="t", description="d", tool_type="function", category="c")
        reg = ToolRegistration(
            tool_id="func:t",
            metadata=meta,
            tool_type=ToolType.FUNCTION,
            handler=lambda: None,
        )
        assert reg.registered_at != ""
        assert reg.last_modified != ""
        assert reg.call_count == 0
        assert reg.success_count == 0
        assert reg.failed_count == 0


class TestRegisterFunctionAndDiscover:
    def test_register_function_and_discover(self, registry):
        func = lambda x: x * 2
        result = registry.register_function("double", "Doubles input", func, category="math")
        assert result is True

        discovered = registry.discover()
        names = [t["name"] for t in discovered]
        assert "double" in names

    def test_register_function_stores_handler(self, registry):
        func = lambda x: x * 2
        registry.register_function("double", "Doubles input", func, category="math")
        tool_id = "func:double"
        assert tool_id in registry._tools
        assert registry._tools[tool_id].handler is func


class TestRegisterRestApiAndDiscoverByType:
    def test_register_rest_api(self, registry):
        result = registry.register_rest_api(
            "weather_api", "Get weather data",
            endpoint="https://api.weather.com/v1",
            method="GET", category="external",
        )
        assert result is True

    def test_discover_by_type_rest(self, registry):
        registry.register_rest_api(
            "weather_api", "Get weather data",
            endpoint="https://api.weather.com/v1",
            method="GET", category="external",
        )
        discovered = registry.discover(tool_type="rest")
        assert len(discovered) == 1
        assert discovered[0]["name"] == "weather_api"
        assert discovered[0]["tool_type"] == "rest"

    def test_discover_by_type_function(self, registry):
        registry.register_function("calc", "Calculator", lambda: None)
        registry.register_rest_api("api", "API", endpoint="/api")
        discovered = registry.discover(tool_type="function")
        assert len(discovered) == 1
        assert discovered[0]["tool_type"] == "function"


class TestExecuteFunction:
    def test_execute_function_success(self, registry):
        def add(a, b):
            return a + b

        registry.register_function("add", "Add two numbers", add, category="math")
        result = registry.execute("add", {"a": 3, "b": 4})
        assert result.success is True
        assert result.data == 7
        assert result.error is None

    def test_execute_function_by_tool_id(self, registry):
        def greet(name):
            return f"hello {name}"

        registry.register_function("greet", "Greet someone", greet)
        result = registry.execute("func:greet", {"name": "world"})
        assert result.success is True
        assert result.data == "hello world"


class TestExecuteNonExistentTool:
    def test_execute_nonexistent_tool(self, registry):
        result = registry.execute("nonexistent", {})
        assert result.success is False
        assert "Tool not found" in result.error
        assert result.tool_name == "nonexistent"

    def test_execute_nonexistent_tool_returns_result(self, registry):
        result = registry.execute("missing_tool", {"x": 1})
        assert result.data is None
        assert result.execution_time_ms >= 0


class TestDiscoverFilters:
    def test_discover_by_pattern(self, registry):
        registry.register_function("data_fetch", "Fetch data", lambda: None)
        registry.register_function("data_push", "Push data", lambda: None)
        registry.register_function("calc", "Calculate", lambda: None)
        discovered = registry.discover(pattern="data")
        assert len(discovered) == 2
        names = [t["name"] for t in discovered]
        assert "data_fetch" in names
        assert "data_push" in names

    def test_discover_by_category(self, registry):
        registry.register_function("tool_a", "A", lambda: None, category="analytics")
        registry.register_function("tool_b", "B", lambda: None, category="analytics")
        registry.register_function("tool_c", "C", lambda: None, category="monitoring")
        discovered = registry.discover(category="analytics")
        assert len(discovered) == 2

    def test_discover_by_capability(self, registry):
        from odap.biz.tool_registry.registry import ToolMetadata, ToolRegistration, ToolType
        meta = ToolMetadata(
            name="cap_tool", description="Has capabilities",
            tool_type="function", category="test",
            capabilities=["query", "analyze"],
        )
        reg = ToolRegistration(
            tool_id="func:cap_tool", metadata=meta,
            tool_type=ToolType.FUNCTION, handler=lambda: None,
        )
        registry._tools["func:cap_tool"] = reg
        discovered = registry.discover(capability="query")
        assert len(discovered) == 1
        assert discovered[0]["name"] == "cap_tool"

    def test_discover_no_filters_returns_all(self, registry):
        registry.register_function("a", "A", lambda: None)
        registry.register_function("b", "B", lambda: None)
        discovered = registry.discover()
        assert len(discovered) >= 2


class TestMCPToolBridge:
    def test_register_mcp_tools(self, mock_base_v2):
        from odap.biz.tool_registry.registry import MCPToolBridge
        bridge = MCPToolBridge()
        tools = [
            {"name": "search", "description": "Search tool", "capabilities": ["query"]},
            {"name": "analyze", "description": "Analyze tool", "capabilities": ["analyze"]},
        ]
        count = bridge.register_mcp_tools("test_server", tools)
        assert count == 2

    def test_discover_mcp_tools(self, mock_base_v2):
        from odap.biz.tool_registry.registry import MCPToolBridge
        bridge = MCPToolBridge()
        tools = [
            {"name": "search", "description": "Search tool"},
            {"name": "analyze", "description": "Analyze tool"},
        ]
        bridge.register_mcp_tools("srv", tools)
        discovered = bridge.discover_mcp_tools()
        assert len(discovered) == 2

    def test_discover_mcp_tools_with_pattern(self, mock_base_v2):
        from odap.biz.tool_registry.registry import MCPToolBridge
        bridge = MCPToolBridge()
        tools = [
            {"name": "search", "description": "Search documents"},
            {"name": "analyze", "description": "Analyze data"},
        ]
        bridge.register_mcp_tools("srv", tools)
        discovered = bridge.discover_mcp_tools(pattern="search")
        assert len(discovered) == 1
        assert "search" in discovered[0].name

    def test_get_mcp_tool(self, mock_base_v2):
        from odap.biz.tool_registry.registry import MCPToolBridge
        bridge = MCPToolBridge()
        tools = [{"name": "lookup", "description": "Lookup tool"}]
        bridge.register_mcp_tools("srv", tools)
        tool = bridge.get_mcp_tool("srv:lookup")
        assert tool is not None
        assert tool.name == "srv:lookup"

    def test_get_mcp_tool_not_found(self, mock_base_v2):
        from odap.biz.tool_registry.registry import MCPToolBridge
        bridge = MCPToolBridge()
        assert bridge.get_mcp_tool("nonexistent") is None


class TestSemanticToolDiscovery:
    def test_index_tool(self, mock_base_v2):
        from odap.biz.tool_registry.registry import SemanticToolDiscovery, ToolMetadata
        sd = SemanticToolDiscovery()
        meta = ToolMetadata(
            name="data_analyzer", description="Analyzes data",
            tool_type="function", category="analytics",
            capabilities=["analyze"], semantic_tags=["data", "analytics"],
        )
        sd.index_tool(meta)
        assert "data_analyzer" in sd._tool_metadata_store

    def test_discover_by_semantics(self, mock_base_v2):
        from odap.biz.tool_registry.registry import SemanticToolDiscovery, ToolMetadata
        sd = SemanticToolDiscovery()
        meta1 = ToolMetadata(
            name="data_analyzer", description="Analyzes data patterns",
            tool_type="function", category="analytics",
            capabilities=["analyze"], semantic_tags=["data"],
        )
        meta2 = ToolMetadata(
            name="report_gen", description="Generates reports",
            tool_type="function", category="reporting",
            capabilities=["query"], semantic_tags=["report"],
        )
        sd.index_tool(meta1)
        sd.index_tool(meta2)
        results = sd.discover_by_semantics("data analyze")
        assert len(results) >= 1
        assert results[0]["tool_name"] == "data_analyzer"
        assert results[0]["score"] > 0

    def test_discover_by_capability(self, mock_base_v2):
        from odap.biz.tool_registry.registry import SemanticToolDiscovery, ToolMetadata
        sd = SemanticToolDiscovery()
        meta = ToolMetadata(
            name="query_tool", description="Query tool",
            tool_type="function", category="query",
            capabilities=["query"],
        )
        sd.index_tool(meta)
        results = sd.discover_by_capability("query")
        assert "query_tool" in results

    def test_discover_by_capability_empty(self, mock_base_v2):
        from odap.biz.tool_registry.registry import SemanticToolDiscovery
        sd = SemanticToolDiscovery()
        results = sd.discover_by_capability("nonexistent")
        assert results == []


class TestToolHealthMonitor:
    def test_record_call_success(self, mock_base_v2):
        from odap.biz.tool_registry.registry import ToolHealthMonitor
        monitor = ToolHealthMonitor()
        monitor.record_call("tool_a", True, 50.0)
        health = monitor.get_health("tool_a")
        assert health is not None
        assert health.total_calls == 1
        assert health.success_calls == 1
        assert health.failed_calls == 0

    def test_record_call_failure(self, mock_base_v2):
        from odap.biz.tool_registry.registry import ToolHealthMonitor
        monitor = ToolHealthMonitor()
        monitor.record_call("tool_b", False, 100.0, error="timeout")
        health = monitor.get_health("tool_b")
        assert health is not None
        assert health.failed_calls == 1
        assert health.last_error == "timeout"

    def test_health_healthy(self, mock_base_v2):
        from odap.biz.tool_registry.registry import ToolHealthMonitor
        monitor = ToolHealthMonitor()
        for _ in range(10):
            monitor.record_call("tool_c", True, 50.0)
        health = monitor.get_health("tool_c")
        assert health.health == "healthy"

    def test_health_degraded_by_error_rate(self, mock_base_v2):
        from odap.biz.tool_registry.registry import ToolHealthMonitor
        monitor = ToolHealthMonitor()
        for _ in range(8):
            monitor.record_call("tool_d", True, 50.0)
        for _ in range(2):
            monitor.record_call("tool_d", False, 50.0)
        health = monitor.get_health("tool_d")
        assert health.health in ("degraded", "unhealthy")

    def test_health_unhealthy_by_error_rate(self, mock_base_v2):
        from odap.biz.tool_registry.registry import ToolHealthMonitor
        monitor = ToolHealthMonitor()
        for _ in range(4):
            monitor.record_call("tool_e", False, 50.0)
        for _ in range(6):
            monitor.record_call("tool_e", True, 50.0)
        health = monitor.get_health("tool_e")
        assert health.health == "unhealthy"

    def test_get_all_health(self, mock_base_v2):
        from odap.biz.tool_registry.registry import ToolHealthMonitor
        monitor = ToolHealthMonitor()
        monitor.record_call("t1", True, 10.0)
        monitor.record_call("t2", True, 20.0)
        all_health = monitor.get_all_health()
        assert len(all_health) == 2

    def test_get_health_nonexistent(self, mock_base_v2):
        from odap.biz.tool_registry.registry import ToolHealthMonitor
        monitor = ToolHealthMonitor()
        assert monitor.get_health("no_such_tool") is None


class TestToolHealthMonitorAlerts:
    def test_alerts_on_degraded(self, mock_base_v2):
        from odap.biz.tool_registry.registry import ToolHealthMonitor
        monitor = ToolHealthMonitor()
        for _ in range(9):
            monitor.record_call("tool_f", True, 50.0)
        monitor.record_call("tool_f", False, 50.0)
        alerts = monitor.get_alerts()
        assert len(alerts) >= 1

    def test_alerts_critical_on_unhealthy(self, mock_base_v2):
        from odap.biz.tool_registry.registry import ToolHealthMonitor
        monitor = ToolHealthMonitor()
        for _ in range(5):
            monitor.record_call("tool_g", False, 50.0)
        critical_alerts = monitor.get_alerts(level="critical")
        assert len(critical_alerts) >= 1
        assert critical_alerts[0]["level"] == "critical"

    def test_clear_alerts_all(self, mock_base_v2):
        from odap.biz.tool_registry.registry import ToolHealthMonitor
        monitor = ToolHealthMonitor()
        for _ in range(5):
            monitor.record_call("tool_h", False, 50.0)
        assert len(monitor.get_alerts()) > 0
        monitor.clear_alerts()
        assert len(monitor.get_alerts()) == 0

    def test_clear_alerts_by_tool(self, mock_base_v2):
        from odap.biz.tool_registry.registry import ToolHealthMonitor
        monitor = ToolHealthMonitor()
        for _ in range(5):
            monitor.record_call("tool_i", False, 50.0)
        for _ in range(5):
            monitor.record_call("tool_j", False, 50.0)
        monitor.clear_alerts(tool_name="tool_i")
        remaining = monitor.get_alerts()
        for a in remaining:
            assert a["tool_name"] != "tool_i"


class TestSemanticDiscovery:
    def test_discover_with_tfidf_scoring(self):
        from odap.biz.tool_registry.semantic_discovery import SemanticDiscovery
        sd = SemanticDiscovery()
        tools = [
            {"name": "data_analyzer", "description": "Analyzes data patterns and trends", "category": "analytics", "tags": ["data", "analysis"]},
            {"name": "report_generator", "description": "Generates reports from data", "category": "reporting", "tags": ["report"]},
            {"name": "data_fetcher", "description": "Fetches data from external sources", "category": "data", "tags": ["data", "fetch"]},
        ]
        results = sd.discover("data analysis", tools, top_k=3)
        assert len(results) <= 3
        assert all("relevance_score" in r for r in results)
        assert results[0]["relevance_score"] >= results[-1]["relevance_score"]

    def test_discover_empty_tools(self):
        from odap.biz.tool_registry.semantic_discovery import SemanticDiscovery
        sd = SemanticDiscovery()
        results = sd.discover("query", [], top_k=5)
        assert results == []

    def test_discover_top_k(self):
        from odap.biz.tool_registry.semantic_discovery import SemanticDiscovery
        sd = SemanticDiscovery()
        tools = [
            {"name": f"tool_{i}", "description": f"Tool number {i}", "category": "test"}
            for i in range(10)
        ]
        results = sd.discover("tool", tools, top_k=3)
        assert len(results) <= 3

    def test_discover_name_boost(self):
        from odap.biz.tool_registry.semantic_discovery import SemanticDiscovery
        sd = SemanticDiscovery()
        tools = [
            {"name": "search", "description": "A generic utility", "category": "util"},
            {"name": "util", "description": "Search for items in the database", "category": "search"},
        ]
        results = sd.discover("search", tools, top_k=2)
        name_matches = [r for r in results if "search" in r["name"]]
        assert len(name_matches) >= 1


class TestCompositeExecutor:
    @pytest.mark.asyncio
    async def test_execute_chain_success(self):
        from odap.biz.tool_registry.composite_executor import CompositeExecutor
        executor = CompositeExecutor()
        tools = [
            {"name": "step1", "params": {"key1": "val1"}},
            {"name": "step2", "params": {"key2": "val2"}},
        ]
        result = await executor.execute_chain(tools, {"initial": "data"})
        assert result["status"] == "success"
        assert result["total_steps"] == 2
        assert len(result["results"]) == 2
        assert all(r["status"] == "success" for r in result["results"])

    @pytest.mark.asyncio
    async def test_execute_chain_with_failure_and_rollback(self):
        from odap.biz.tool_registry.composite_executor import CompositeExecutor
        executor = CompositeExecutor(tool_registry=None)
        rollback_called = []

        def sync_rollback(input_data):
            rollback_called.append(input_data)

        tools = [
            {"name": "step1", "params": {}, "rollback": sync_rollback},
            {"name": "fail_step", "params": {}},
        ]
        executor._execute_single = AsyncMock(side_effect=[
            {"step1_result": "ok"},
            Exception("boom"),
        ])
        result = await executor.execute_chain(tools, {"input": "data"})
        assert result["status"] == "failed"
        assert result["failed_at_step"] == 2
        assert result["failed_tool"] == "fail_step"
        assert result["rolled_back"] is True
        assert len(rollback_called) == 1

    @pytest.mark.asyncio
    async def test_execute_chain_empty(self):
        from odap.biz.tool_registry.composite_executor import CompositeExecutor
        executor = CompositeExecutor()
        result = await executor.execute_chain([], {"input": "data"})
        assert result["status"] == "success"
        assert result["total_steps"] == 0

    @pytest.mark.asyncio
    async def test_execute_chain_async_rollback(self):
        from odap.biz.tool_registry.composite_executor import CompositeExecutor
        executor = CompositeExecutor()
        async_rollback_called = []

        async def async_rollback(input_data):
            async_rollback_called.append(input_data)

        tools = [
            {"name": "step1", "params": {}, "rollback": async_rollback},
            {"name": "step2", "params": {}},
        ]
        executor._execute_single = AsyncMock(side_effect=[
            {"result": "ok"},
            Exception("fail"),
        ])
        result = await executor.execute_chain(tools, {"data": "test"})
        assert result["status"] == "failed"
        assert len(async_rollback_called) == 1


class TestToolChains:
    def test_register_and_get_tool_chain(self, registry):
        from odap.biz.tool_registry.registry import ToolChain, ToolChainStep
        chain = ToolChain(
            chain_id="chain_1",
            name="test_chain",
            description="A test chain",
            steps=[
                ToolChainStep(tool_name="step_a", input_mapping={}, output_mapping={}),
                ToolChainStep(tool_name="step_b", input_mapping={}, output_mapping={}),
            ],
        )
        result = registry.register_tool_chain(chain)
        assert result is True
        retrieved = registry.get_tool_chain("chain_1")
        assert retrieved is not None
        assert retrieved.name == "test_chain"
        assert len(retrieved.steps) == 2

    def test_get_nonexistent_chain(self, registry):
        assert registry.get_tool_chain("no_such_chain") is None

    def test_execute_chain_not_found(self, registry):
        with pytest.raises(ValueError, match="Tool chain not found"):
            registry.execute_chain("missing_chain", {})

    def test_execute_chain_with_functions(self, registry):
        from odap.biz.tool_registry.registry import ToolChain, ToolChainStep
        registry.register_function("add", "Add", lambda a, b: a + b, category="math")
        chain = ToolChain(
            chain_id="math_chain",
            name="math_ops",
            description="Math operations",
            steps=[
                ToolChainStep(tool_name="add", input_mapping={"a": "a", "b": "b"}, output_mapping={}),
            ],
        )
        registry.register_tool_chain(chain)
        results = registry.execute_chain("math_chain", {"a": 2, "b": 3})
        assert len(results) >= 1
        assert results[0].success is True
        assert results[0].data == 5


class TestToolRegistryExecutionHistory:
    def test_execution_history(self, registry):
        registry.register_function("hist_tool", "History tool", lambda: "result")
        registry.execute("hist_tool", {})
        history = registry.get_execution_history()
        assert len(history) >= 1
        assert history[-1].tool_name == "hist_tool"

    def test_execution_history_limit(self, registry):
        registry.register_function("lim_tool", "Limit tool", lambda: "x")
        for _ in range(5):
            registry.execute("lim_tool", {})
        history = registry.get_execution_history(limit=2)
        assert len(history) <= 2


class TestToolRegistryHealthReport:
    def test_health_report(self, registry):
        registry.register_function("hr_tool", "Health report tool", lambda: "ok")
        registry.execute("hr_tool", {})
        report = registry.get_health_report()
        assert "total_tools" in report
        assert "healthy_count" in report
        assert "alerts" in report
        assert report["total_tools"] >= 1
