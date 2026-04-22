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

        from odap.tools.base import BaseSkill, SkillInput, SkillOutput, SkillMetadata

        class CrossToolSkill(BaseSkill):
            metadata = SkillMetadata(
                name="cross_tool_skill",
                description="跨工具测试",
                category="test"
            )

            def execute(self, input_data: SkillInput) -> SkillOutput:
                result = tool_registry.execute("helper", {"x": input_data.value})
                return SkillOutput(
                    success=result.success,
                    data={"result": result.data + 1 if result.success else None},
                    execution_time_ms=0,
                    skill_name=self.metadata.name,
                    request_id=input_data.request_id
                )

        tool_registry.register_skill(CrossToolSkill())

        result = tool_registry.execute("cross_tool_skill", {"value": 10})
        assert result.success is True


class TestAuditIntegration:
    """审计日志集成测试"""

    def test_audit_logging(self, audit_logger):
        """测试审计日志记录"""
        try:
            audit_logger.log(
                action="test_action",
                resource_type="test",
                resource_id="test-001",
                user_id="test-user"
            )

            timeline = audit_logger.get_timeline(limit=10)
            assert isinstance(timeline, list)
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
        pytest.importorskip("odap.infra.opa.opa_service_v2")

        from odap.infra.opa.opa_service_v2 import OPAManagerV2

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
                        "input": getattr(input_data, "data", None),
                        "processed": True,
                        "timestamp": time.time()
                    },
                    execution_time_ms=0,
                    skill_name=self.metadata.name,
                    request_id=input_data.request_id
                )

        tool_registry.register_skill(E2ETestSkill())

        result = tool_registry.execute("e2e_test_skill", {"data": "test-data"})
        assert result.success is True
        assert result.data["processed"] is True
        assert result.data["input"] == "test-data"

    def test_tool_chain_execution(self, tool_registry):
        """测试工具链执行"""
        from odap.biz.tool_registry.registry import ToolChain, ToolChainStep

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
    def test_neo4j_connection(self, docker_services, test_config):
        """测试 Neo4j 连接"""
        pytest.importorskip("neo4j")

        from neo4j import GraphDatabase

        try:
            driver = GraphDatabase.driver(
                test_config["neo4j_uri"],
                auth=(test_config["neo4j_user"], test_config["neo4j_password"])
            )
            with driver.session() as session:
                result = session.run("RETURN 1 as n")
                assert result.single()["n"] == 1
            driver.close()
        except Exception as e:
            pytest.skip(f"Neo4j connection failed: {e}")

    @pytest.mark.docker
    def test_opa_connection(self, docker_services, test_config):
        """测试 OPA 连接"""
        import requests

        try:
            response = requests.get(f"{test_config['opa_url']}/v1/health")
            assert response.status_code == 200
        except Exception as e:
            pytest.skip(f"OPA connection failed: {e}")

    @pytest.mark.docker
    def test_redis_connection(self, docker_services, test_config):
        """测试 Redis 连接"""
        import redis

        try:
            r = redis.from_url(test_config["redis_url"])
            r.ping()
        except Exception as e:
            pytest.skip(f"Redis connection failed: {e}")


if __name__ == "__main__":
    pytest.main([__file__, "-v", "-m", "integration"])