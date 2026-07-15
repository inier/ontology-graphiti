import pytest
import sys
import os
from unittest.mock import MagicMock, patch

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..', '..'))

from odap.biz.platform.workspace.impl.workspace import WorkspaceManager
from odap.biz.platform.workspace.impl.isolation import IsolationManager
from odap.biz.platform.workspace.models.workspace import Workspace, WorkspaceStatus, WorkspaceType, WorkspaceConfig
from odap.biz.platform.workspace.models.isolation import IsolationLevel, ResourceQuota, NetworkPolicy


@pytest.fixture
def mock_storage():
    storage = MagicMock()
    storage.save_workspace = MagicMock()
    storage.update_workspace = MagicMock()
    storage.delete_workspace = MagicMock()
    storage.list_workspaces = MagicMock(return_value=[])
    storage.save_isolation_policy = MagicMock()
    storage.get_isolation_policy = MagicMock(return_value={})
    storage.update_isolation_policy = MagicMock()
    return storage


@pytest.fixture
def workspace_manager(mock_storage):
    with patch('odap.biz.platform.workspace.impl.workspace.Storage') as MockStorage:
        MockStorage.return_value = mock_storage
        manager = WorkspaceManager()
    return manager


@pytest.fixture
def isolation_manager(mock_storage):
    with patch('odap.biz.platform.workspace.impl.isolation.Storage') as MockStorage:
        MockStorage.return_value = mock_storage
        manager = IsolationManager()
    return manager


def _make_workspace(**overrides):
    defaults = {
        "id": "ws-001",
        "name": "Test Workspace",
        "description": "A test workspace",
        "type": WorkspaceType.DEFAULT,
        "status": WorkspaceStatus.ACTIVE,
        "config": WorkspaceConfig(),
        "owner": "admin",
        "members": [],
        "bound_ontology_ids": [],
    }
    defaults.update(overrides)
    return Workspace(**defaults)


class TestWorkspaceManager:

    def test_create_workspace(self, workspace_manager, mock_storage):
        workspace = workspace_manager.create_workspace(
            name="Test Workspace",
            description="A test workspace",
            owner="admin"
        )

        assert workspace.name == "Test Workspace"
        assert workspace.description == "A test workspace"
        assert workspace.owner == "admin"
        assert workspace.status == WorkspaceStatus.ACTIVE
        assert mock_storage.save_workspace.called
        assert mock_storage.update_workspace.called

    def test_get_workspace(self, workspace_manager, mock_storage):
        ws = _make_workspace()
        mock_storage.get_workspace.return_value = ws

        result = workspace_manager.get_workspace("ws-001")

        assert result is not None
        assert result.id == "ws-001"
        assert result.name == "Test Workspace"
        mock_storage.get_workspace.assert_called_once_with("ws-001")

    def test_update_workspace(self, workspace_manager, mock_storage):
        ws = _make_workspace()
        mock_storage.get_workspace.return_value = ws

        result = workspace_manager.update_workspace("ws-001", {"name": "Updated Name"})

        assert result.name == "Updated Name"
        assert mock_storage.update_workspace.called

    def test_update_workspace_not_found(self, workspace_manager, mock_storage):
        mock_storage.get_workspace.return_value = None

        with pytest.raises(ValueError, match="Workspace not found"):
            workspace_manager.update_workspace("nonexistent", {"name": "X"})

    def test_delete_workspace(self, workspace_manager, mock_storage):
        ws = _make_workspace()
        mock_storage.get_workspace.return_value = ws

        result = workspace_manager.delete_workspace("ws-001")

        assert result is True
        assert mock_storage.update_workspace.called
        assert mock_storage.delete_workspace.called

    def test_delete_workspace_not_found(self, workspace_manager, mock_storage):
        mock_storage.get_workspace.return_value = None

        result = workspace_manager.delete_workspace("nonexistent")

        assert result is False

    def test_list_workspaces(self, workspace_manager, mock_storage):
        ws1 = _make_workspace(id="ws-001", name="Workspace 1")
        ws2 = _make_workspace(id="ws-002", name="Workspace 2")
        mock_storage.list_workspaces.return_value = [ws1, ws2]

        result = workspace_manager.list_workspaces()

        assert len(result) == 2
        assert result[0].name == "Workspace 1"
        assert result[1].name == "Workspace 2"

    def test_activate_deactivate(self, workspace_manager, mock_storage):
        ws = _make_workspace(status=WorkspaceStatus.INACTIVE)
        mock_storage.get_workspace.return_value = ws

        activated = workspace_manager.activate_workspace("ws-001")
        assert activated.status == WorkspaceStatus.ACTIVE

        mock_storage.get_workspace.return_value = activated
        deactivated = workspace_manager.deactivate_workspace("ws-001")
        assert deactivated.status == WorkspaceStatus.INACTIVE

    def test_add_remove_member(self, workspace_manager, mock_storage):
        ws = _make_workspace(members=[])
        mock_storage.get_workspace.return_value = ws

        result = workspace_manager.add_member("ws-001", "user-1")
        assert "user-1" in result.members

        mock_storage.get_workspace.return_value = result
        result = workspace_manager.remove_member("ws-001", "user-1")
        assert "user-1" not in result.members

    def test_bind_unbind_ontology(self, workspace_manager, mock_storage):
        ws = _make_workspace(bound_ontology_ids=[])
        mock_storage.get_workspace.return_value = ws

        result = workspace_manager.bind_ontology("ws-001", "ont-1")
        assert "ont-1" in result.bound_ontology_ids

        mock_storage.get_workspace.return_value = result
        result = workspace_manager.unbind_ontology("ws-001", "ont-1")
        assert "ont-1" not in result.bound_ontology_ids


class TestIsolationManager:

    def test_create_isolation_policy(self, isolation_manager, mock_storage):
        quota = ResourceQuota(cpu="2", memory="4Gi")
        policy = NetworkPolicy(allowed_ips=["10.0.0.0/8"])

        result = isolation_manager.create_isolation_policy(
            workspace_id="ws-001",
            isolation_level=IsolationLevel.HIGH,
            resource_quota=quota,
            network_policy=policy
        )

        assert result["workspace_id"] == "ws-001"
        assert result["isolation_level"] == "high"
        assert result["resource_quota"]["cpu"] == "2"
        assert result["resource_quota"]["memory"] == "4Gi"
        assert "10.0.0.0/8" in result["network_policy"]["allowed_ips"]
        mock_storage.save_isolation_policy.assert_called_once()

    def test_get_isolation_policy(self, isolation_manager, mock_storage):
        expected = {"workspace_id": "ws-001", "isolation_level": "standard"}
        mock_storage.get_isolation_policy.return_value = expected

        result = isolation_manager.get_isolation_policy("ws-001")

        assert result["workspace_id"] == "ws-001"
        assert result["isolation_level"] == "standard"
        mock_storage.get_isolation_policy.assert_called_once_with("ws-001")

    def test_update_isolation_policy(self, isolation_manager, mock_storage):
        existing = {"workspace_id": "ws-001", "isolation_level": "standard"}
        mock_storage.get_isolation_policy.return_value = existing

        result = isolation_manager.update_isolation_policy("ws-001", {"isolation_level": "strict"})

        assert result["isolation_level"] == "strict"
        mock_storage.update_isolation_policy.assert_called_once()

    def test_update_isolation_policy_not_found(self, isolation_manager, mock_storage):
        mock_storage.get_isolation_policy.return_value = {}

        with pytest.raises(ValueError, match="Isolation policy not found"):
            isolation_manager.update_isolation_policy("nonexistent", {"isolation_level": "high"})

    def test_enforce_isolation(self, isolation_manager, mock_storage):
        mock_storage.get_isolation_policy.return_value = {
            "workspace_id": "ws-001",
            "isolation_level": "high"
        }

        result = isolation_manager.enforce_isolation("ws-001")

        assert result is True

    def test_validate_isolation(self, isolation_manager, mock_storage):
        mock_storage.get_isolation_policy.return_value = {
            "workspace_id": "ws-001",
            "isolation_level": "standard",
            "resource_quota": {"cpu": "2"},
            "network_policy": {"enable_firewall": True}
        }

        result = isolation_manager.validate_isolation("ws-001")

        assert result["status"] in ("success", "warning")
        assert result["isolation_level"] == "standard"

    def test_get_resource_usage(self, isolation_manager, mock_storage):
        result = isolation_manager.get_resource_usage("ws-001")

        assert result["workspace_id"] == "ws-001"
        assert "storage_bytes" in result or "entity_count" in result

    def test_check_quota_violation(self, isolation_manager, mock_storage):
        mock_storage.get_isolation_policy.return_value = {
            "workspace_id": "ws-001",
            "isolation_level": "standard",
            "resource_quota": {"storage": "1Ki", "max_connections": 0}
        }

        with patch.object(isolation_manager, 'get_resource_usage', return_value={
            "workspace_id": "ws-001",
            "entity_count": 5,
            "storage_bytes": 1048576,
            "storage_mb": 1.0
        }):
            violations = isolation_manager.check_quota_violation("ws-001")

        assert len(violations) >= 1
