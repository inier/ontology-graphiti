"""
工具注册表测试
"""

import pytest
from unittest.mock import MagicMock, patch


class TestToolRegistry:
    """工具注册表测试"""

    def test_register_skill_tool(self, tool_registry):
        """测试注册 Skill 工具"""
        from odap.tools.base import BaseSkill, SkillInput, SkillOutput, SkillMetadata

        class TestSkill(BaseSkill):
            metadata = SkillMetadata(
                name="test_tool_registry_skill",
                description="测试工具注册表",
                category="analysis"
            )

            def execute(self, input_data: SkillInput) -> SkillOutput:
                return SkillOutput(
                    success=True,
                    data={"result": "test"},
                    execution_time_ms=0,
                    skill_name=self.metadata.name,
                    request_id=input_data.request_id
                )

        result = tool_registry.register_skill(TestSkill())
        assert result is True

        tools = tool_registry.discover(pattern="test_tool_registry_skill")
        assert len(tools) > 0
        assert tools[0]["name"] == "test_tool_registry_skill"

    def test_register_native_function(self, tool_registry):
        """测试注册原生函数"""
        def add_numbers(x: int, y: int) -> int:
            return x + y

        result = tool_registry.register_function(
            name="add_numbers",
            description="加法运算",
            func=add_numbers,
            category="computation"
        )
        assert result is True

        tools = tool_registry.discover(pattern="add_numbers")
        assert len(tools) > 0

    def test_discover_by_type(self, tool_registry):
        """测试按类型发现工具"""
        skills = tool_registry.discover(tool_type="skill")
        assert isinstance(skills, list)

        functions = tool_registry.discover(tool_type="function")
        assert isinstance(functions, list)

    def test_execute_skill(self, tool_registry):
        """测试执行 Skill"""
        from odap.tools.base import BaseSkill, SkillInput, SkillOutput, SkillMetadata

        class EchoSkill(BaseSkill):
            metadata = SkillMetadata(
                name="echo_skill",
                description="回显技能",
                category="operations"
            )

            def execute(self, input_data: SkillInput) -> SkillOutput:
                return SkillOutput(
                    success=True,
                    data={"echo": getattr(input_data, "value", "default")},
                    execution_time_ms=0,
                    skill_name=self.metadata.name,
                    request_id=input_data.request_id
                )

        tool_registry.register_skill(EchoSkill())
        result = tool_registry.execute("echo_skill", {"value": "hello"})

        assert result.success is True
        assert result.data.get("echo") == "hello"

    def test_execute_native_function(self, tool_registry):
        """测试执行原生函数"""
        def multiply(x: int, y: int) -> int:
            return x * y

        tool_registry.register_function(
            name="multiply",
            description="乘法运算",
            func=multiply,
            category="computation"
        )

        result = tool_registry.execute("multiply", {"x": 6, "y": 7})
        assert result.success is True
        assert result.data == 42

    def test_tool_not_found(self, tool_registry):
        """测试工具不存在"""
        result = tool_registry.execute("nonexistent_tool", {})
        assert result.success is False
        assert "not found" in result.error.lower()

    def test_health_report(self, tool_registry):
        """测试健康报告"""
        report = tool_registry.get_health_report()
        assert "total_tools" in report
        assert "healthy_count" in report
        assert "total_calls" in report

    def test_execution_history(self, tool_registry):
        """测试执行历史"""
        history = tool_registry.get_execution_history(limit=10)
        assert isinstance(history, list)

    def test_tool_chain(self, tool_registry):
        """测试工具链"""
        from odap.biz.tool_registry.registry import ToolChain, ToolChainStep

        def step1(input1: str) -> str:
            return input1.upper()

        def step2(input1: str) -> str:
            return input1 + "!"

        tool_registry.register_function("step1", "步骤1", step1)
        tool_registry.register_function("step2", "步骤2", step2)

        chain = ToolChain(
            chain_id="test_chain",
            name="测试链",
            description="测试工具链",
            steps=[
                ToolChainStep(tool_name="step1", input_mapping={"input1": "text"}, output_mapping={"result": "upper"}),
                ToolChainStep(tool_name="step2", input_mapping={"input1": "upper.result"}, output_mapping={"result": "final"})
            ]
        )

        result = tool_registry.register_tool_chain(chain)
        assert result is True

        chain = tool_registry.get_tool_chain("test_chain")
        assert chain is not None
        assert chain.chain_id == "test_chain"


class TestSemanticDiscovery:
    """语义发现测试"""

    def test_semantic_indexing(self):
        """测试语义索引"""
        from odap.biz.tool_registry.registry import SemanticToolDiscovery, ToolMetadata

        discovery = SemanticToolDiscovery()

        metadata = ToolMetadata(
            name="radar_search",
            description="搜索雷达系统",
            tool_type="skill",
            category="intelligence",
            capabilities=["query", "analyze"],
            semantic_tags=["radar", "search", "detection"]
        )

        discovery.index_tool(metadata)

        results = discovery.discover_by_semantics("寻找雷达")
        assert isinstance(results, list)

    def test_capability_discovery(self):
        """测试能力发现"""
        from odap.biz.tool_registry.registry import SemanticToolDiscovery, ToolMetadata

        discovery = SemanticToolDiscovery()

        metadata = ToolMetadata(
            name="analyze_radar",
            description="分析雷达数据",
            tool_type="skill",
            category="analysis",
            capabilities=["analyze"]
        )

        discovery.index_tool(metadata)

        tools = discovery.discover_by_capability("analyze")
        assert isinstance(tools, list)


class TestHealthMonitor:
    """健康监控测试"""

    def test_record_call_success(self):
        """测试记录成功调用"""
        from odap.biz.tool_registry.registry import ToolHealthMonitor

        monitor = ToolHealthMonitor()
        monitor.record_call("test_tool", success=True, latency_ms=100)

        health = monitor.get_health("test_tool")
        assert health is not None
        assert health.total_calls == 1
        assert health.success_calls == 1

    def test_record_call_failure(self):
        """测试记录失败调用"""
        from odap.biz.tool_registry.registry import ToolHealthMonitor

        monitor = ToolHealthMonitor()
        monitor.record_call("test_tool", success=False, latency_ms=100, error="Test error")

        health = monitor.get_health("test_tool")
        assert health is not None
        assert health.failed_calls == 1
        assert health.last_error == "Test error"

    def test_health_calculation(self):
        """测试健康状态计算"""
        from odap.biz.tool_registry.registry import ToolHealthMonitor

        monitor = ToolHealthMonitor()

        for i in range(10):
            monitor.record_call("healthy_tool", success=True, latency_ms=50)

        health = monitor.get_health("healthy_tool")
        assert health.health == "healthy"

        for i in range(5):
            monitor.record_call("degraded_tool", success=False, latency_ms=50)

        health = monitor.get_health("degraded_tool")
        assert health.health in ["degraded", "unhealthy"]

    def test_alerts(self):
        """测试告警"""
        from odap.biz.tool_registry.registry import ToolHealthMonitor

        monitor = ToolHealthMonitor()

        for i in range(10):
            monitor.record_call("failing_tool", success=False, latency_ms=100)

        alerts = monitor.get_alerts()
        assert len(alerts) > 0


if __name__ == "__main__":
    pytest.main([__file__, "-v"])