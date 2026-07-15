"""测试隔离服务 (IsolationService)"""

import pytest
from unittest.mock import MagicMock, patch

from odap.biz.platform.workspace.services.isolation_service import IsolationService
from odap.biz.platform.workspace.models.isolation import IsolationLevel, ResourceQuota, NetworkPolicy


@pytest.fixture
def mock_manager():
    manager = MagicMock()
    return manager


@pytest.fixture
def isolation_service(mock_manager):
    service = IsolationService()
    service.manager = mock_manager
    return service


class TestCreateIsolationPolicy:
    def test_create_policy_success(self, isolation_service, mock_manager):
        """创建隔离策略成功"""
        mock_manager.create_isolation_policy.return_value = {
            "workspace_id": "ws-001",
            "isolation_level": "standard",
            "resource_quota": {"cpu": "1", "memory": "2Gi"},
            "network_policy": {"enable_firewall": True},
            "created_at": "2025-01-01T00:00:00",
        }
        result = isolation_service.create_isolation_policy(
            workspace_id="ws-001",
            isolation_level=IsolationLevel.STANDARD,
        )
        assert result["workspace_id"] == "ws-001"
        assert result["isolation_level"] == "standard"
        mock_manager.create_isolation_policy.assert_called_once()

    def test_create_policy_with_custom_quota(self, isolation_service, mock_manager):
        """创建隔离策略时使用自定义配额"""
        quota = ResourceQuota(cpu="2", memory="4Gi", storage="10Gi")
        mock_manager.create_isolation_policy.return_value = {
            "workspace_id": "ws-002",
            "isolation_level": "high",
            "resource_quota": quota.model_dump(),
        }
        result = isolation_service.create_isolation_policy(
            workspace_id="ws-002",
            isolation_level=IsolationLevel.HIGH,
            resource_quota=quota,
        )
        assert result["resource_quota"]["cpu"] == "2"
        assert result["resource_quota"]["memory"] == "4Gi"

    def test_create_strict_policy_with_network(self, isolation_service, mock_manager):
        """创建严格隔离策略时带网络策略"""
        network = NetworkPolicy(enable_firewall=True, allowed_ports=[443])
        mock_manager.create_isolation_policy.return_value = {
            "workspace_id": "ws-003",
            "isolation_level": "strict",
            "network_policy": network.model_dump(),
        }
        result = isolation_service.create_isolation_policy(
            workspace_id="ws-003",
            isolation_level=IsolationLevel.STRICT,
            network_policy=network,
        )
        assert result["network_policy"]["enable_firewall"] is True
        assert 443 in result["network_policy"]["allowed_ports"]


class TestGetIsolationPolicy:
    def test_get_existing_policy(self, isolation_service, mock_manager):
        """获取已存在的隔离策略"""
        mock_manager.get_isolation_policy.return_value = {
            "workspace_id": "ws-001",
            "isolation_level": "standard",
        }
        result = isolation_service.get_isolation_policy("ws-001")
        assert result["workspace_id"] == "ws-001"
        assert result["isolation_level"] == "standard"

    def test_get_nonexistent_policy_returns_error(self, isolation_service, mock_manager):
        """获取不存在的隔离策略返回错误"""
        mock_manager.get_isolation_policy.return_value = None
        result = isolation_service.get_isolation_policy("ws-999")
        assert result["status"] == "error"
        assert "not found" in result["message"]


class TestUpdateIsolationPolicy:
    def test_update_policy_success(self, isolation_service, mock_manager):
        """更新隔离策略成功"""
        mock_manager.update_isolation_policy.return_value = {
            "workspace_id": "ws-001",
            "isolation_level": "high",
            "resource_quota": {"cpu": "0.5"},
        }
        result = isolation_service.update_isolation_policy(
            workspace_id="ws-001",
            updates={"isolation_level": "high"},
        )
        assert result["isolation_level"] == "high"
        mock_manager.update_isolation_policy.assert_called_once_with("ws-001", {"isolation_level": "high"})

    def test_update_nonexistent_policy_returns_error(self, isolation_service, mock_manager):
        """更新不存在的策略返回错误"""
        mock_manager.update_isolation_policy.side_effect = ValueError("Isolation policy not found")
        result = isolation_service.update_isolation_policy(
            workspace_id="ws-999",
            updates={"isolation_level": "strict"},
        )
        assert result["status"] == "error"
        assert "not found" in result["message"]


class TestEnforceIsolation:
    def test_enforce_success(self, isolation_service, mock_manager):
        """执行隔离成功"""
        mock_manager.enforce_isolation.return_value = True
        result = isolation_service.enforce_isolation("ws-001")
        assert result["status"] == "success"
        assert result["message"] == "Isolation enforced"

    def test_enforce_failure(self, isolation_service, mock_manager):
        """执行隔离失败"""
        mock_manager.enforce_isolation.return_value = False
        result = isolation_service.enforce_isolation("ws-001")
        assert result["status"] == "error"
        assert result["message"] == "Failed to enforce isolation"


class TestValidateIsolation:
    def test_validate_returns_manager_result(self, isolation_service, mock_manager):
        """验证隔离返回 manager 的结果"""
        mock_manager.validate_isolation.return_value = {
            "status": "success",
            "isolation_level": "standard",
            "checks": [{"check": "data_isolation", "passed": True}],
        }
        result = isolation_service.validate_isolation("ws-001")
        assert result["status"] == "success"
        assert len(result["checks"]) == 1


class TestCheckQuotaViolation:
    def test_no_violations(self, isolation_service, mock_manager):
        """无配额违规"""
        mock_manager.check_quota_violation.return_value = []
        result = isolation_service.check_quota_violation("ws-001")
        assert result["violation_count"] == 0
        assert result["violations"] == []

    def test_with_violations(self, isolation_service, mock_manager):
        """存在配额违规"""
        mock_manager.check_quota_violation.return_value = [
            {"resource": "storage", "severity": "critical"},
        ]
        result = isolation_service.check_quota_violation("ws-001")
        assert result["violation_count"] == 1
        assert result["violations"][0]["resource"] == "storage"
