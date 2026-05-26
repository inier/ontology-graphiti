import ast
import glob
from pathlib import Path

import pytest

PROJECT_ROOT = Path(__file__).parent.parent.parent

AGENT_DIR = PROJECT_ROOT / "odap" / "biz" / "core" / "agent"
COGNITION_DIR = PROJECT_ROOT / "odap" / "biz" / "core" / "cognition"
QUERY_DIR = PROJECT_ROOT / "odap" / "infra" / "query"


class TestQueryFirstGuard:
    """
    架构守卫测试: Query First 原则
    确保 Agent 模块不直接导入 GraphManager，应通过 QueryService
    """

    DIRECT_GRAPH_IMPORTS = [
        "from odap.infra.graph import",
        "from odap.infra.graph.graph_service import",
        "import odap.infra.graph",
    ]

    ALLOWED_FILES = {
        "odap/infra/query/sources/entity_source.py",
        "odap/infra/query/sources/topo_source.py",
        "odap/infra/graph/graph_service.py",
        "odap/infra/graph/__init__.py",
        "odap/biz/core/ontology/services/pipeline_service.py",
        "odap/biz/core/ontology/hot_write.py",
        "odap/biz/core/ontology/management_engine.py",
        "odap/biz/integration/frontend_compat/api/routes.py",
        "odap/web/api/app.py",
        "odap/biz/core/agent/intelligence_agent.py",
        "odap/biz/core/agent/swarm_orchestrator.py",
    }

    def test_agent_modules_no_direct_graph_import(self):
        """Agent 模块禁止直接导入 GraphManager"""
        agent_files = glob.glob(str(AGENT_DIR / "*.py"))
        violations = []
        for f in agent_files:
            rel_path = str(Path(f).relative_to(PROJECT_ROOT)).replace("\\", "/")
            if rel_path in self.ALLOWED_FILES:
                continue
            content = Path(f).read_text(encoding="utf-8")
            for pattern in self.DIRECT_GRAPH_IMPORTS:
                if pattern in content:
                    violations.append(f"{rel_path}: found '{pattern}'")
        assert not violations, (
            f"Agent modules should use QueryService, not GraphManager directly:\n"
            + "\n".join(violations)
        )

    def test_cognition_modules_no_direct_graph_import(self):
        """认知模块禁止直接导入 GraphManager"""
        cognition_files = glob.glob(str(COGNITION_DIR / "*.py"))
        violations = []
        for f in cognition_files:
            rel_path = str(Path(f).relative_to(PROJECT_ROOT)).replace("\\", "/")
            if rel_path in self.ALLOWED_FILES:
                continue
            content = Path(f).read_text(encoding="utf-8")
            for pattern in self.DIRECT_GRAPH_IMPORTS:
                if pattern in content:
                    violations.append(f"{rel_path}: found '{pattern}'")
        assert not violations, (
            f"Cognition modules should use QueryService, not GraphManager directly:\n"
            + "\n".join(violations)
        )

    def test_query_service_exists(self):
        """QueryService 模块必须存在"""
        assert (QUERY_DIR / "service.py").exists(), "QueryService module not found"
        assert (QUERY_DIR / "protocols.py").exists(), "QueryService protocols not found"
        assert (QUERY_DIR / "parser.py").exists(), "QueryService parser not found"

    def test_query_service_sources_exist(self):
        """QueryService 数据源实现必须存在"""
        sources_dir = QUERY_DIR / "sources"
        assert (sources_dir / "schema_source.py").exists(), "SchemaSource not found"
        assert (sources_dir / "entity_source.py").exists(), "EntitySource not found"
        assert (sources_dir / "topo_source.py").exists(), "TopoSource not found"

    def test_graph_manager_has_traversal_methods(self):
        """GraphManager 必须提供图遍历方法"""
        graph_service = PROJECT_ROOT / "odap" / "infra" / "graph" / "graph_service.py"
        content = graph_service.read_text(encoding="utf-8")
        assert "def get_neighbors(" in content, "GraphManager.get_neighbors() not found"
        assert "def traverse(" in content, "GraphManager.traverse() not found"

    def test_knowledge_navigator_supports_query_service(self):
        """KnowledgeNavigator 必须支持 QueryService"""
        cognition_file = COGNITION_DIR / "user_cognition_engine.py"
        content = cognition_file.read_text(encoding="utf-8")
        assert "query_service" in content, "KnowledgeNavigator does not support query_service"

    def test_write_guard_exists(self):
        """Agent 写操作安全守卫必须存在"""
        guard_file = PROJECT_ROOT / "odap" / "infra" / "openharness" / "query_guard_hook.py"
        assert guard_file.exists(), "QueryServiceWriteGuard not found"
        content = guard_file.read_text(encoding="utf-8")
        assert "QueryServiceWriteGuard" in content
        assert "WRITE_TOOLS" in content
