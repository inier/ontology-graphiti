import pytest
from unittest.mock import AsyncMock, MagicMock, patch, PropertyMock

from odap.biz.action_service.executor import ActionExecutor
from odap.biz.action_service.schemas import (
    ActionRequest,
    ActionExecutionResult,
    ActionRequestStatus,
)


class TestActionExecutorInit:
    def test_lazy_properties_none_on_init(self):
        executor = ActionExecutor()
        assert executor._action_storage is None
        assert executor._oms is None
        assert executor._graph_manager is None
        assert executor._opa_manager is None


class TestValidate:
    @pytest.mark.asyncio
    async def test_valid_params(self):
        executor = ActionExecutor()
        record = {
            "parameters": {"name": "test", "value": 42},
            "target_object_type": "Host",
        }
        action_type_def = {
            "parameters": [
                {"name": "name", "required": True},
                {"name": "value", "required": True},
            ],
            "target_object_type": "Host",
        }
        result = await executor._validate(record, action_type_def)
        assert result["valid"] is True
        assert result["errors"] == []

    @pytest.mark.asyncio
    async def test_missing_required_params(self):
        executor = ActionExecutor()
        record = {
            "parameters": {"name": "test"},
            "target_object_type": "Host",
        }
        action_type_def = {
            "parameters": [
                {"name": "name", "required": True},
                {"name": "value", "required": True},
                {"name": "priority", "required": True},
            ],
            "target_object_type": "Host",
        }
        result = await executor._validate(record, action_type_def)
        assert result["valid"] is False
        assert len(result["errors"]) == 2
        assert "Missing required parameter: value" in result["errors"]
        assert "Missing required parameter: priority" in result["errors"]

    @pytest.mark.asyncio
    async def test_target_type_mismatch(self):
        executor = ActionExecutor()
        record = {
            "parameters": {"name": "test"},
            "target_object_type": "Network",
        }
        action_type_def = {
            "parameters": [{"name": "name", "required": True}],
            "target_object_type": "Host",
        }
        result = await executor._validate(record, action_type_def)
        assert result["valid"] is False
        assert any("Target object type mismatch" in e for e in result["errors"])

    @pytest.mark.asyncio
    async def test_no_target_type_in_def_passes(self):
        executor = ActionExecutor()
        record = {
            "parameters": {"name": "test"},
            "target_object_type": "Host",
        }
        action_type_def = {
            "parameters": [{"name": "name", "required": True}],
        }
        result = await executor._validate(record, action_type_def)
        assert result["valid"] is True

    @pytest.mark.asyncio
    async def test_none_required_param_treated_as_missing(self):
        executor = ActionExecutor()
        record = {
            "parameters": {"name": "test", "value": None},
            "target_object_type": "Host",
        }
        action_type_def = {
            "parameters": [
                {"name": "name", "required": True},
                {"name": "value", "required": True},
            ],
            "target_object_type": "Host",
        }
        result = await executor._validate(record, action_type_def)
        assert result["valid"] is False
        assert "Missing required parameter: value" in result["errors"]


class TestCheckOPA:
    @pytest.mark.asyncio
    async def test_no_opa_configured_fail_closed(self):
        executor = ActionExecutor()
        record = {"requested_by": "admin", "action_type_id": "update_status"}
        action_type_def = {"opa_policy": "some_policy"}
        with patch.object(type(executor), 'opa', new_callable=PropertyMock, return_value=None):
            result = await executor._check_opa(record, action_type_def)
        assert result["allow"] is False
        assert "fail-closed" in result["reason"]

    @pytest.mark.asyncio
    async def test_opa_allowing(self):
        executor = ActionExecutor()
        mock_opa = MagicMock()
        mock_opa.check_permission_abac = MagicMock(return_value={"allow": True, "reason": "permitted"})

        record = {
            "requested_by": "admin",
            "action_type_id": "update_status",
            "target_object_id": "host-1",
            "agent_id": "agent-1",
        }
        action_type_def = {"opa_policy": "policy_a"}
        with patch.object(type(executor), 'opa', new_callable=PropertyMock, return_value=mock_opa):
            result = await executor._check_opa(record, action_type_def)
        assert result["allow"] is True
        mock_opa.check_permission_abac.assert_called_once_with(
            user="admin",
            action="update_status",
            resource="host-1",
            environment={"agent_id": "agent-1"},
        )

    @pytest.mark.asyncio
    async def test_opa_denying(self):
        executor = ActionExecutor()
        mock_opa = MagicMock()
        mock_opa.check_permission_abac = MagicMock(return_value={"allow": False, "reason": "forbidden"})

        record = {
            "requested_by": "unauthorized_user",
            "action_type_id": "delete",
            "target_object_id": "host-1",
        }
        action_type_def = {"opa_policy": "policy_a"}
        with patch.object(type(executor), 'opa', new_callable=PropertyMock, return_value=mock_opa):
            result = await executor._check_opa(record, action_type_def)
        assert result["allow"] is False

    @pytest.mark.asyncio
    async def test_no_opa_policy_configured_allows(self):
        executor = ActionExecutor()
        mock_opa = MagicMock()

        record = {"requested_by": "admin"}
        action_type_def = {}
        with patch.object(type(executor), 'opa', new_callable=PropertyMock, return_value=mock_opa):
            result = await executor._check_opa(record, action_type_def)
        assert result["allow"] is True
        assert "No OPA policy" in result["reason"]

    @pytest.mark.asyncio
    async def test_opa_exception_fail_closed(self):
        executor = ActionExecutor()
        mock_opa = MagicMock()
        mock_opa.check_permission_abac = MagicMock(side_effect=ConnectionError("OPA down"))

        record = {"requested_by": "admin", "action_type_id": "delete"}
        action_type_def = {"opa_policy": "policy_a"}
        with patch.object(type(executor), 'opa', new_callable=PropertyMock, return_value=mock_opa):
            result = await executor._check_opa(record, action_type_def)
        assert result["allow"] is False
        assert "fail-closed" in result["reason"]


class TestDoExecute:
    @pytest.mark.asyncio
    async def test_update_status_action(self):
        executor = ActionExecutor()
        mock_graph = MagicMock()
        executor._graph_manager = mock_graph

        record = {
            "action_record_id": "ar_test",
            "target_object_id": "host-1",
            "target_object_type": "Host",
            "parameters": {"property": "status", "value": "active"},
        }
        action_type_def = {"name": "update_status"}

        result = await executor._do_execute(record, action_type_def)
        assert result.success is True
        assert "Updated status=active on host-1" in result.message
        mock_graph.update_entity.assert_called_once_with("host-1", {"status": "active"})

    @pytest.mark.asyncio
    async def test_create_action(self):
        executor = ActionExecutor()
        mock_graph = MagicMock()
        executor._graph_manager = mock_graph

        record = {
            "action_record_id": "ar_test",
            "target_object_id": "new-entity-1",
            "target_object_type": "Host",
            "parameters": {"name": "WebServer"},
        }
        action_type_def = {"name": "create"}

        result = await executor._do_execute(record, action_type_def)
        assert result.success is True
        assert "Created Host 'WebServer'" in result.message
        mock_graph.add_entity.assert_called_once_with(
            entity_id="new-entity-1",
            entity_type="Host",
            properties={"name": "WebServer"},
        )

    @pytest.mark.asyncio
    async def test_delete_action(self):
        executor = ActionExecutor()
        mock_graph = MagicMock()
        executor._graph_manager = mock_graph

        record = {
            "action_record_id": "ar_test",
            "target_object_id": "host-1",
            "target_object_type": "Host",
            "parameters": {},
        }
        action_type_def = {"name": "delete"}

        result = await executor._do_execute(record, action_type_def)
        assert result.success is True
        assert "Deleted entity host-1" in result.message
        mock_graph.delete_entity.assert_called_once_with("host-1")

    @pytest.mark.asyncio
    async def test_link_action(self):
        executor = ActionExecutor()
        mock_graph = MagicMock()
        executor._graph_manager = mock_graph

        record = {
            "action_record_id": "ar_test",
            "target_object_id": "host-1",
            "target_object_type": "Host",
            "parameters": {"target_id": "host-2", "link_type": "connected_to"},
        }
        action_type_def = {"name": "link"}

        result = await executor._do_execute(record, action_type_def)
        assert result.success is True
        assert "Created link [connected_to] from host-1 to host-2" in result.message
        mock_graph.add_relationship.assert_called_once_with("host-1", "host-2", "connected_to", {})

    @pytest.mark.asyncio
    async def test_unknown_action_with_properties(self):
        executor = ActionExecutor()
        mock_graph = MagicMock()
        executor._graph_manager = mock_graph

        record = {
            "action_record_id": "ar_test",
            "target_object_id": "host-1",
            "target_object_type": "Host",
            "parameters": {"severity": "high", "owner": "team-a"},
        }
        action_type_def = {"name": "escalate"}

        result = await executor._do_execute(record, action_type_def)
        assert result.success is True
        mock_graph.update_entity.assert_called_once_with("host-1", {"severity": "high", "owner": "team-a"})

    @pytest.mark.asyncio
    async def test_unknown_action_no_properties(self):
        executor = ActionExecutor()
        mock_graph = MagicMock()
        executor._graph_manager = mock_graph

        record = {
            "action_record_id": "ar_test",
            "target_object_id": "host-1",
            "target_object_type": "Host",
            "parameters": {"entity_type": "Host", "target_id": "x", "link_type": "y"},
        }
        action_type_def = {"name": "unknown_action"}

        result = await executor._do_execute(record, action_type_def)
        assert result.success is False
        assert "Unknown action type" in result.message

    @pytest.mark.asyncio
    async def test_execute_exception_returns_failure(self):
        executor = ActionExecutor()
        mock_graph = MagicMock()
        mock_graph.update_entity.side_effect = RuntimeError("graph error")
        executor._graph_manager = mock_graph

        record = {
            "action_record_id": "ar_test",
            "target_object_id": "host-1",
            "target_object_type": "Host",
            "parameters": {"property": "status", "value": "active"},
        }
        action_type_def = {"name": "update_status"}

        result = await executor._do_execute(record, action_type_def)
        assert result.success is False
        assert "Execution failed" in result.message

    @pytest.mark.asyncio
    async def test_modify_action_alias(self):
        executor = ActionExecutor()
        mock_graph = MagicMock()
        executor._graph_manager = mock_graph

        record = {
            "action_record_id": "ar_test",
            "target_object_id": "host-1",
            "target_object_type": "Host",
            "parameters": {"property": "phase", "value": "deployed"},
        }
        action_type_def = {"name": "modify"}

        result = await executor._do_execute(record, action_type_def)
        assert result.success is True
        mock_graph.update_entity.assert_called_once_with("host-1", {"phase": "deployed"})

    @pytest.mark.asyncio
    async def test_add_action_alias(self):
        executor = ActionExecutor()
        mock_graph = MagicMock()
        executor._graph_manager = mock_graph

        record = {
            "action_record_id": "ar_test",
            "target_object_id": "new-1",
            "target_object_type": "Service",
            "parameters": {"name": "API"},
        }
        action_type_def = {"name": "add"}

        result = await executor._do_execute(record, action_type_def)
        assert result.success is True
        mock_graph.add_entity.assert_called_once()

    @pytest.mark.asyncio
    async def test_remove_action_alias(self):
        executor = ActionExecutor()
        mock_graph = MagicMock()
        executor._graph_manager = mock_graph

        record = {
            "action_record_id": "ar_test",
            "target_object_id": "host-1",
            "target_object_type": "Host",
            "parameters": {},
        }
        action_type_def = {"name": "remove"}

        result = await executor._do_execute(record, action_type_def)
        assert result.success is True
        mock_graph.delete_entity.assert_called_once_with("host-1")

    @pytest.mark.asyncio
    async def test_relate_action_alias(self):
        executor = ActionExecutor()
        mock_graph = MagicMock()
        executor._graph_manager = mock_graph

        record = {
            "action_record_id": "ar_test",
            "target_object_id": "a",
            "target_object_type": "Host",
            "parameters": {"target_id": "b", "link_type": "depends_on"},
        }
        action_type_def = {"name": "relate"}

        result = await executor._do_execute(record, action_type_def)
        assert result.success is True
        mock_graph.add_relationship.assert_called_once_with("a", "b", "depends_on", {})


class TestSubmitAction:
    @pytest.mark.asyncio
    async def test_full_flow_success(self):
        executor = ActionExecutor()
        mock_storage = MagicMock()
        mock_storage.create_record = MagicMock(return_value={
            "action_record_id": "ar_full_test",
            "action_type_id": "update_status",
            "target_object_id": "host-1",
            "target_object_type": "Host",
            "parameters": {"property": "status", "value": "active"},
            "status": "pending",
            "requested_by": "admin",
            "reason": "",
            "agent_id": None,
        })
        mock_storage.update_status = MagicMock(return_value={
            "action_record_id": "ar_full_test",
            "status": "completed",
        })
        mock_storage.get_record = MagicMock(return_value={
            "action_record_id": "ar_full_test",
            "action_type_id": "update_status",
            "target_object_id": "host-1",
            "target_object_type": "Host",
            "parameters": {"property": "status", "value": "active"},
            "status": "completed",
            "requested_by": "admin",
            "reason": "",
            "agent_id": None,
            "execution_result": {"success": True},
        })
        executor._action_storage = mock_storage

        mock_oms = MagicMock()
        mock_oms.get_action_type = MagicMock(return_value={
            "name": "update_status",
            "parameters": [{"name": "property", "required": True}, {"name": "value", "required": True}],
            "target_object_type": "Host",
        })
        executor._oms = mock_oms

        mock_graph = MagicMock()
        executor._graph_manager = mock_graph

        request = ActionRequest(
            action_type_id="update_status",
            target_object_id="host-1",
            target_object_type="Host",
            parameters={"property": "status", "value": "active"},
            requested_by="admin",
        )

        with patch.object(type(executor), 'opa', new_callable=PropertyMock, return_value=None):
            with patch.object(executor, "_check_opa", new_callable=AsyncMock, return_value={"allow": True}):
                with patch("odap.biz.action_service.feedback_loop.get_feedback_loop"):
                    record = await executor.submit_action(request)

        assert record["status"] == "completed"

    @pytest.mark.asyncio
    async def test_opa_rejection(self):
        executor = ActionExecutor()
        mock_storage = MagicMock()
        mock_storage.create_record = MagicMock(return_value={
            "action_record_id": "ar_reject_test",
            "action_type_id": "delete",
            "target_object_id": "host-1",
            "target_object_type": "Host",
            "parameters": {},
            "status": "pending",
            "requested_by": "unauthorized",
            "reason": "",
            "agent_id": None,
        })
        mock_storage.update_status = MagicMock(return_value={
            "action_record_id": "ar_reject_test",
            "status": "rejected",
        })
        mock_storage.get_record = MagicMock(return_value={
            "action_record_id": "ar_reject_test",
            "action_type_id": "delete",
            "target_object_id": "host-1",
            "target_object_type": "Host",
            "parameters": {},
            "status": "rejected",
            "requested_by": "unauthorized",
            "reason": "",
            "agent_id": None,
            "opa_decision": {"allow": False, "reason": "denied"},
        })
        executor._action_storage = mock_storage

        mock_oms = MagicMock()
        mock_oms.get_action_type = MagicMock(return_value={
            "name": "delete",
            "parameters": [],
            "target_object_type": "Host",
        })
        executor._oms = mock_oms

        request = ActionRequest(
            action_type_id="delete",
            target_object_id="host-1",
            target_object_type="Host",
            parameters={},
            requested_by="unauthorized",
        )

        with patch.object(executor, "_check_opa", new_callable=AsyncMock, return_value={"allow": False, "reason": "denied"}):
            record = await executor.submit_action(request)

        assert record["status"] == "rejected"

    @pytest.mark.asyncio
    async def test_unknown_action_type_raises(self):
        executor = ActionExecutor()
        mock_oms = MagicMock()
        mock_oms.get_action_type = MagicMock(return_value=None)
        executor._oms = mock_oms

        request = ActionRequest(
            action_type_id="nonexistent",
            target_object_id="host-1",
            target_object_type="Host",
        )

        with pytest.raises(ValueError, match="not found in OMS"):
            await executor.submit_action(request)

    @pytest.mark.asyncio
    async def test_validation_failure_rejects(self):
        executor = ActionExecutor()
        mock_storage = MagicMock()
        mock_storage.create_record = MagicMock(return_value={
            "action_record_id": "ar_val_fail",
            "action_type_id": "update_status",
            "target_object_id": "host-1",
            "target_object_type": "Network",
            "parameters": {},
            "status": "pending",
            "requested_by": "admin",
            "reason": "",
            "agent_id": None,
        })
        mock_storage.update_status = MagicMock(return_value={
            "action_record_id": "ar_val_fail",
            "status": "rejected",
        })
        mock_storage.get_record = MagicMock(return_value={
            "action_record_id": "ar_val_fail",
            "status": "rejected",
            "action_type_id": "update_status",
            "target_object_id": "host-1",
            "target_object_type": "Network",
            "parameters": {},
            "requested_by": "admin",
            "reason": "",
            "agent_id": None,
        })
        executor._action_storage = mock_storage

        mock_oms = MagicMock()
        mock_oms.get_action_type = MagicMock(return_value={
            "name": "update_status",
            "parameters": [{"name": "property", "required": True}],
            "target_object_type": "Host",
        })
        executor._oms = mock_oms

        request = ActionRequest(
            action_type_id="update_status",
            target_object_id="host-1",
            target_object_type="Network",
            parameters={},
        )

        record = await executor.submit_action(request)
        assert record["status"] == "rejected"

    @pytest.mark.asyncio
    async def test_confirmation_required_stops_at_approved(self):
        executor = ActionExecutor()
        mock_storage = MagicMock()
        mock_storage.create_record = MagicMock(return_value={
            "action_record_id": "ar_confirm",
            "action_type_id": "delete",
            "target_object_id": "host-1",
            "target_object_type": "Host",
            "parameters": {},
            "status": "pending",
            "requested_by": "admin",
            "reason": "",
            "agent_id": None,
        })
        mock_storage.update_status = MagicMock(return_value={
            "action_record_id": "ar_confirm",
            "status": "approved",
        })
        mock_storage.get_record = MagicMock(return_value={
            "action_record_id": "ar_confirm",
            "status": "approved",
            "action_type_id": "delete",
            "target_object_id": "host-1",
            "target_object_type": "Host",
            "parameters": {},
            "requested_by": "admin",
            "reason": "",
            "agent_id": None,
        })
        executor._action_storage = mock_storage

        mock_oms = MagicMock()
        mock_oms.get_action_type = MagicMock(return_value={
            "name": "delete",
            "parameters": [],
            "target_object_type": "Host",
            "confirmation_required": True,
        })
        executor._oms = mock_oms

        request = ActionRequest(
            action_type_id="delete",
            target_object_id="host-1",
            target_object_type="Host",
        )

        with patch.object(executor, "_check_opa", new_callable=AsyncMock, return_value={"allow": True}):
            record = await executor.submit_action(request)

        assert record["status"] == "approved"
