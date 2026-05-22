import pytest
import sys
import os
from unittest.mock import MagicMock, patch

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..', '..'))

from odap.biz.roles.opa_sync import RoleOPASync


@pytest.fixture
def opa_sync():
    return RoleOPASync()


@pytest.fixture
def mock_opa_manager():
    manager = MagicMock()
    manager.load_policy.return_value = True
    manager.delete_policy.return_value = True
    return manager


def test_sync_role_to_opa_with_mock_opa(opa_sync, mock_opa_manager):
    opa_sync._opa_manager = mock_opa_manager
    role_data = {
        "id": "r_abc123",
        "name": "analyst",
        "role_type": "member",
        "permissions": [
            {"id": "p1", "name": "read", "actions": ["view_intelligence", "analyze_data"]},
            {"id": "p2", "name": "write", "actions": ["generate_reports"]}
        ]
    }
    result = opa_sync.sync_role_to_opa(role_data)
    assert result is True
    mock_opa_manager.load_policy.assert_called_once()
    call_args = mock_opa_manager.load_policy.call_args
    assert call_args[0][0] == "role_r_abc123"
    rego = call_args[0][1]
    assert 'package odap.roles.analyst' in rego
    assert 'input.role == "analyst"' in rego
    assert '"view_intelligence"' in rego
    assert '"analyze_data"' in rego
    assert '"generate_reports"' in rego


def test_sync_role_to_opa_with_string_permissions(opa_sync, mock_opa_manager):
    opa_sync._opa_manager = mock_opa_manager
    role_data = {
        "id": "r_def456",
        "name": "operator",
        "role_type": "member",
        "permissions": ["read", "write"]
    }
    result = opa_sync.sync_role_to_opa(role_data)
    assert result is True
    call_args = mock_opa_manager.load_policy.call_args
    rego = call_args[0][1]
    assert '"read"' in rego
    assert '"write"' in rego


def test_remove_role_from_opa(opa_sync, mock_opa_manager):
    opa_sync._opa_manager = mock_opa_manager
    result = opa_sync.remove_role_from_opa("r_abc123")
    assert result is True
    mock_opa_manager.delete_policy.assert_called_once_with("role_r_abc123")


def test_generate_rego_produces_valid_rego(opa_sync):
    rego = opa_sync._generate_rego("commander", "system_admin", [
        {"id": "p1", "actions": ["view_intelligence", "command_units"]},
        {"id": "p2", "actions": ["authorize_attacks"]}
    ])
    assert 'package odap.roles.commander' in rego
    assert 'default allow = false' in rego
    assert 'input.role == "commander"' in rego
    assert 'input.action in' in rego
    assert '"view_intelligence"' in rego
    assert '"command_units"' in rego
    assert '"authorize_attacks"' in rego


def test_generate_rego_with_string_permissions(opa_sync):
    rego = opa_sync._generate_rego("pilot", "member", ["fly", "navigate"])
    assert 'package odap.roles.pilot' in rego
    assert '"fly"' in rego
    assert '"navigate"' in rego


def test_generate_rego_with_empty_permissions(opa_sync):
    rego = opa_sync._generate_rego("guest", "guest", [])
    assert 'package odap.roles.guest' in rego
    assert '""' in rego


def test_sync_role_when_opa_unavailable(opa_sync):
    opa_sync._opa_manager = None
    with patch.object(
        type(opa_sync), 'opa_manager',
        new_callable=lambda: property(lambda self: None)
    ):
        result = opa_sync.sync_role_to_opa({"id": "1", "name": "test", "permissions": []})
        assert result is False


def test_remove_role_when_opa_unavailable(opa_sync):
    opa_sync._opa_manager = None
    with patch.object(
        type(opa_sync), 'opa_manager',
        new_callable=lambda: property(lambda self: None)
    ):
        result = opa_sync.remove_role_from_opa("1")
        assert result is False


def test_sync_role_when_opa_load_fails(opa_sync, mock_opa_manager):
    mock_opa_manager.load_policy.return_value = False
    opa_sync._opa_manager = mock_opa_manager
    result = opa_sync.sync_role_to_opa({"id": "1", "name": "test", "permissions": []})
    assert result is False


def test_remove_role_when_opa_delete_fails(opa_sync, mock_opa_manager):
    mock_opa_manager.delete_policy.return_value = False
    opa_sync._opa_manager = mock_opa_manager
    result = opa_sync.remove_role_from_opa("1")
    assert result is False


def test_sync_role_handles_exception(opa_sync, mock_opa_manager):
    mock_opa_manager.load_policy.side_effect = Exception("OPA connection error")
    opa_sync._opa_manager = mock_opa_manager
    result = opa_sync.sync_role_to_opa({"id": "1", "name": "test", "permissions": []})
    assert result is False


def test_remove_role_handles_exception(opa_sync, mock_opa_manager):
    mock_opa_manager.delete_policy.side_effect = Exception("OPA connection error")
    opa_sync._opa_manager = mock_opa_manager
    result = opa_sync.remove_role_from_opa("1")
    assert result is False
