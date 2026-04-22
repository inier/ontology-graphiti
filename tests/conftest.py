"""
pytest 配置文件
ODAP 集成测试框架配置
"""

import pytest
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


def pytest_configure(config):
    """pytest 初始化配置"""
    config.addinivalue_line("markers", "integration: 集成测试标记")
    config.addinivalue_line("markers", "unit: 单元测试标记")
    config.addinivalue_line("markers", "slow: 慢速测试标记")
    config.addinivalue_line("markers", "docker: 需要 Docker 的测试")


def pytest_collection_modifyitems(config, items):
    """修改测试收集"""
    for item in items:
        if "integration" in item.nodeid:
            item.add_marker(pytest.mark.integration)
        elif "unit" in item.nodeid:
            item.add_marker(pytest.mark.unit)


@pytest.fixture(scope="session")
def test_config():
    """测试配置"""
    return {
        "neo4j_uri": os.getenv("NEO4J_URI", "bolt://localhost:7687"),
        "neo4j_user": os.getenv("NEO4J_USER", "neo4j"),
        "neo4j_password": os.getenv("NEO4J_PASSWORD", "neo4j123456"),
        "opa_url": os.getenv("OPA_URL", "http://localhost:8181"),
        "redis_url": os.getenv("REDIS_URL", "redis://localhost:6379"),
        "use_docker": os.getenv("USE_DOCKER", "false").lower() == "true",
    }


@pytest.fixture(scope="session")
def docker_services(test_config):
    """Docker 服务管理器"""
    if not test_config["use_docker"]:
        pytest.skip("Docker not enabled, skipping docker tests")

    import docker
    client = docker.from_env()

    services = {
        "neo4j": {
            "image": "neo4j:latest",
            "ports": {"7474/tcp": 7474, "7687/tcp": 7687},
            "environment": {
                "NEO4J_AUTH": "neo4j/neo4j123456",
                "NEO4J_dbms_memory_heap_max__size": "2G"
            }
        },
        "opa": {
            "image": "openpolicyagent/opa:0.58.0",
            "ports": {"8181/tcp": 8181},
            "command": "run --server --log-level=info"
        },
        "redis": {
            "image": "redis:6",
            "ports": {"6379/tcp": 6379}
        }
    }

    started_containers = []

    try:
        for name, spec in services.items():
            container = client.containers.run(
                spec["image"],
                detach=True,
                ports=spec.get("ports", {}),
                environment=spec.get("environment", {}),
                command=spec.get("command"),
                name=f"odap-test-{name}",
                remove=True
            )
            started_containers.append(container)
            print(f"Started {name} container: {container.short_id}")

        yield

    finally:
        for container in started_containers:
            try:
                container.stop(timeout=5)
                print(f"Stopped container: {container.short_id}")
            except Exception as e:
                print(f"Error stopping container: {e}")


@pytest.fixture
def mock_graph_client(mocker):
    """模拟图数据库客户端"""
    mock_client = mocker.MagicMock()
    mock_client.query.return_value = {"results": []}
    mock_client.create_node.return_value = {"node_id": "test-123"}
    return mock_client


@pytest.fixture
def mock_opa_client(mocker):
    """模拟 OPA 客户端"""
    mock_client = mocker.MagicMock()
    mock_client.check_permission.return_value = True
    return mock_client


@pytest.fixture
def sample_ontology_doc():
    """示例本体文档"""
    return {
        "doc_id": "test-doc-001",
        "version": "1.0.0",
        "entities": [
            {
                "entity_id": "entity-001",
                "name": "雷达系统A",
                "type": "radar",
                "properties": {
                    "location": "A区",
                    "status": "active"
                }
            }
        ],
        "relationships": [
            {
                "source_id": "entity-001",
                "target_id": "entity-002",
                "type": "detects",
                "properties": {}
            }
        ]
    }


@pytest.fixture
def sample_user_context():
    """示例用户上下文"""
    return {
        "user_id": "test-user-001",
        "role": "pilot",
        "clearance_level": "secret",
        "workspace_id": "ws-001",
        "scenario_id": "scenario-001"
    }


@pytest.fixture
def skill_registry():
    """获取 Skill 注册表"""
    from odap.tools.base_v2 import get_registry_v2
    return get_registry_v2()


@pytest.fixture
def tool_registry():
    """获取工具注册表"""
    from odap.biz.tool_registry import get_tool_registry
    return get_tool_registry()


@pytest.fixture
def audit_logger():
    """获取审计日志器"""
    from odap.infra.security.audit_logger_v2 import get_audit_logger
    return get_audit_logger()
