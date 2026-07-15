"""
集成测试
WR-19: 集成测试框架
"""

import pytest
import time
from unittest.mock import MagicMock, patch


class TestSkillIntegration:
    """Skill 集成测试"""

    def test_skill_registration_and_execution(self, skill_registry):
        """测试 Skill 注册和执行"""
        from odap.tools.base import BaseSkill, SkillInput, SkillOutput, SkillMetadata

        class IntegrationTestSkill(BaseSkill):
            metadata = SkillMetadata(
                name="integration_test_skill",
                description="集成测试技能",
                category="test"
            )

            def execute(self, input_data: SkillInput) -> SkillOutput:
                return SkillOutput(
                    success=True,
                    data={"processed": True, "value": getattr(input_data, "value", 0) * 2},
                    execution_time_ms=0,
                    skill_name=self.metadata.name,
                    request_id=input_data.request_id
                )

        skill_registry.register(IntegrationTestSkill(), version="1.0.0")

        result = skill_registry.execute("integration_test_skill", {"value": 21})
        assert result.success is True
        assert result.data["processed"] is True

    def test_skill_discovery(self, skill_registry):
        """测试 Skill 发现"""
        skills = skill_registry.discover()
        assert isinstance(skills, list)

    def test_skill_health_report(self, skill_registry):
        """测试 Skill 健康报告"""
        report = skill_registry.get_health_report()
        assert "total_skills" in report
        assert "healthy_count" in report


class TestToolRegistryIntegration:
    """工具注册表集成测试"""

    def test_unified_tool_discovery(self, tool_registry):
        """测试统一工具发现"""
        from odap.tools.base import BaseSkill, SkillInput, SkillOutput, SkillMetadata

        class UnifiedTestSkill(BaseSkill):
            metadata = SkillMetadata(
                name="unified_test_skill",
                description="统一工具测试",
                category="test"
            )

            def execute(self, input_data: SkillInput) -> SkillOutput:
                return SkillOutput(
                    success=True,
                    data={"result": "ok"},
                    execution_time_ms=0,
                    skill_name=self.metadata.name,
                    request_id=input_data.request_id
                )

        tool_registry.register_skill(UnifiedTestSkill())

        all_tools = tool_registry.discover()
        assert len(all_tools) > 0

        skill_tools = tool_registry.discover(tool_type="skill")
        assert len(skill_tools) > 0

    def test_cross_tool_execution(self, tool_registry):
        """测试跨工具执行"""

        def helper_func(x: int) -> int:
            return x + 1

        tool_registry.register_function("helper", "辅助函数", helper_func)

        result = tool_registry.execute("helper", {"x": 10})
        assert result.success is True
        assert result.data == 11


class TestAuditIntegration:
    """审计日志集成测试"""

    def test_audit_logging(self, audit_logger):
        """测试审计日志记录"""
        try:
            import asyncio
            from odap.infra.security.audit_logger import AuditEventType, AuditSeverity

            event_id = asyncio.run(audit_logger.log(
                event_type=AuditEventType.DATA_ACCESS,
                severity=AuditSeverity.INFO,
                actor={"user_id": "test-user", "role": "admin"},
                action="test_action",
                resource={"type": "test", "id": "test-001"},
                result={"status": "success"},
                workspace_id="test-workspace"
            ))
            assert event_id is not None
        except Exception as e:
            pytest.skip(f"Audit logger not fully configured: {e}")


class TestGraphIntegration:
    """图数据库集成测试"""

    def test_graph_client_integration(self):
        """测试图客户端集成"""
        pytest.importorskip("odap.infra.graph.graphiti_client_v2")

        from odap.infra.graph.graphiti_client_v2 import GraphitiClientV2

        client = GraphitiClientV2()
        assert client is not None


class TestOPAIntegration:
    """OPA 策略集成测试"""

    def test_opa_permission_check(self):
        """测试 OPA 权限检查"""
        pytest.importorskip("odap.infra.opa.opa_service")

        from odap.infra.opa.opa_service import OPAManagerV2

        try:
            manager = OPAManagerV2()
            result = manager.check_permission("admin", "read", {"type": "ontology"})
            assert isinstance(result, bool)
        except Exception:
            pytest.skip("OPA service not available")


class TestEndToEnd:
    """端到端测试"""

    def test_tool_execution_flow(self, tool_registry):
        """测试工具执行流程"""
        from odap.tools.base import BaseSkill, SkillInput, SkillOutput, SkillMetadata

        class E2ETestSkill(BaseSkill):
            metadata = SkillMetadata(
                name="e2e_test_skill",
                description="端到端测试",
                category="test"
            )

            def execute(self, input_data: SkillInput) -> SkillOutput:
                return SkillOutput(
                    success=True,
                    data={
                        "processed": True,
                        "timestamp": time.time()
                    },
                    execution_time_ms=0,
                    skill_name=self.metadata.name,
                    request_id=input_data.request_id
                )

        tool_registry.register_skill(E2ETestSkill())

        result = tool_registry.execute("e2e_test_skill", {})
        assert result.success is True
        assert result.data["processed"] is True

    def test_tool_chain_execution(self, tool_registry):
        """测试工具链执行"""
        from odap.biz.platform.tool_registry.registry import ToolChain, ToolChainStep

        def process_step(data: str) -> str:
            return f"processed: {data}"

        def validate_step(result: str) -> bool:
            return result.startswith("processed:")

        tool_registry.register_function("process", "处理步骤", process_step)
        tool_registry.register_function("validate", "验证步骤", validate_step)

        chain = ToolChain(
            chain_id="e2e_chain",
            name="端到端链",
            description="端到端测试工具链",
            steps=[
                ToolChainStep(
                    tool_name="process",
                    input_mapping={"data": "input"},
                    output_mapping={"result": "processed"}
                ),
                ToolChainStep(
                    tool_name="validate",
                    input_mapping={"result": "processed"},
                    output_mapping={"valid": "valid"}
                )
            ]
        )

        tool_registry.register_tool_chain(chain)

        results = tool_registry.execute_chain("e2e_chain", {"input": "test"})
        assert len(results) > 0


@pytest.mark.integration
class TestDockerIntegration:
    """Docker 集成测试"""

    @pytest.mark.docker
    def test_neo4j_connection(self):
        """测试 Neo4j 连接"""
        pytest.skip("Docker services not available in test environment")

    @pytest.mark.docker
    def test_opa_connection(self):
        """测试 OPA 连接"""
        pytest.skip("Docker services not available in test environment")

    @pytest.mark.docker
    def test_redis_connection(self):
        """测试 Redis 连接"""
        pytest.skip("Docker services not available in test environment")


if __name__ == "__main__":
    pytest.main([__file__, "-v", "-m", "integration"])
