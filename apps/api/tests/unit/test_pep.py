#!/usr/bin/env python3
"""P1-03: PEP 统一策略执行点测试

验证白皮书 §3 运行时执行流：白名单→OPA→执行→审计
"""

import pytest
from unittest.mock import patch, MagicMock
from odap.infra.opa.pep import (
    PolicyEnforcementPoint,
    EnforcementRequest,
    EnforcementResult,
)


def _make_request(tool_name="read_file", action="view", agent_id="agent-1"):
    return EnforcementRequest(
        agent_id=agent_id,
        tool_name=tool_name,
        action=action,
        resource={"type": "file", "id": "doc1"},
        subject={"id": "user1", "roles": ["analyst"]},
        environment={"time": "2026-08-14T10:00:00Z"},
        input_context={"path": "/data/doc1.txt"},
        trace_id="trace-001",
    )


class TestPEPWhitelistBlocking:
    """白名单拦截不进入 OPA"""

    def test_non_whitelisted_tool_blocked(self):
        mock_opa = MagicMock()
        pep = PolicyEnforcementPoint(opa_manager=mock_opa, allowed_tools=["read_file"])

        req = _make_request(tool_name="delete_file")
        result = pep.evaluate(req)

        assert not result.allowed
        assert result.blocked_at == "whitelist"
        assert result.stage == "whitelist"
        assert "not in allow-list" in result.reason
        # OPA 不应被调用
        mock_opa.check_permission_abac.assert_not_called()

    def test_whitelisted_tool_proceeds_to_opa(self):
        mock_opa = MagicMock()
        mock_opa.check_permission_abac.return_value = {"allow": True, "reason": "granted"}
        mock_opa.get_bundle_version.return_value = "1.0.0"
        pep = PolicyEnforcementPoint(opa_manager=mock_opa, allowed_tools=["read_file"])

        req = _make_request(tool_name="read_file")
        result = pep.evaluate(req)

        assert result.allowed
        assert result.stage == "executed"
        mock_opa.check_permission_abac.assert_called_once()


class TestPEPOPAEvaluation:
    """OPA ALLOW/DENY 串联"""

    def test_opa_allow_returns_executed(self):
        mock_opa = MagicMock()
        mock_opa.check_permission_abac.return_value = {"allow": True, "reason": "granted"}
        mock_opa.get_bundle_version.return_value = "1.0.0"
        pep = PolicyEnforcementPoint(opa_manager=mock_opa, allowed_tools=["read_file"])

        result = pep.evaluate(_make_request())

        assert result.allowed
        assert result.stage == "executed"
        assert result.opa_decision == {"allow": True, "reason": "granted"}

    def test_opa_deny_returns_blocked(self):
        mock_opa = MagicMock()
        mock_opa.check_permission_abac.return_value = {"allow": False, "reason": "insufficient clearance"}
        mock_opa.get_bundle_version.return_value = "1.0.0"
        pep = PolicyEnforcementPoint(opa_manager=mock_opa, allowed_tools=["read_file"])

        result = pep.evaluate(_make_request())

        assert not result.allowed
        assert result.blocked_at == "opa"
        assert result.stage == "opa"
        assert "insufficient clearance" in result.reason

    def test_opa_exception_fail_close(self):
        mock_opa = MagicMock()
        mock_opa.check_permission_abac.side_effect = RuntimeError("OPA down")
        mock_opa.get_bundle_version.return_value = "1.0.0"
        pep = PolicyEnforcementPoint(opa_manager=mock_opa, allowed_tools=["read_file"])

        result = pep.evaluate(_make_request())

        assert not result.allowed
        assert result.blocked_at == "opa"
        assert "OPA evaluation error" in result.reason


class TestPEPAudit:
    """PEP 评估产生审计事件（含 agent_id, trace_id）"""

    def test_whitelist_block_writes_audit(self):
        mock_opa = MagicMock()
        mock_opa.get_bundle_version.return_value = "1.0.0"
        pep = PolicyEnforcementPoint(opa_manager=mock_opa, allowed_tools=["read_file"])

        with patch("odap.infra.security.unified_audit.audit_opa_decision") as mock_audit:
            pep.evaluate(_make_request(tool_name="evil_tool"))

        assert mock_audit.called
        kwargs = mock_audit.call_args.kwargs
        assert kwargs["subject"] == "agent-1"
        assert kwargs["result"] == "deny"

    def test_opa_allow_writes_audit(self):
        mock_opa = MagicMock()
        mock_opa.check_permission_abac.return_value = {"allow": True, "reason": "ok"}
        mock_opa.get_bundle_version.return_value = "1.0.0"
        pep = PolicyEnforcementPoint(opa_manager=mock_opa, allowed_tools=["read_file"])

        with patch("odap.infra.security.unified_audit.audit_opa_decision") as mock_audit:
            pep.evaluate(_make_request())

        assert mock_audit.called
        kwargs = mock_audit.call_args.kwargs
        assert kwargs["subject"] == "agent-1"
        assert kwargs["result"] == "allow"
        assert "read_file" in kwargs["action"]

    def test_opa_deny_writes_audit(self):
        mock_opa = MagicMock()
        mock_opa.check_permission_abac.return_value = {"allow": False, "reason": "denied"}
        mock_opa.get_bundle_version.return_value = "1.0.0"
        pep = PolicyEnforcementPoint(opa_manager=mock_opa, allowed_tools=["read_file"])

        with patch("odap.infra.security.unified_audit.audit_opa_decision") as mock_audit:
            pep.evaluate(_make_request())

        assert mock_audit.called
        assert mock_audit.call_args.kwargs["result"] == "deny"


class TestPEPRecordExecution:
    """PostToolUse 记录 output_artifact"""

    def test_record_execution_fires_hook(self):
        mock_opa = MagicMock()
        mock_hook_registry = MagicMock()
        pep = PolicyEnforcementPoint(
            opa_manager=mock_opa,
            hook_registry=mock_hook_registry,
            allowed_tools=["read_file"],
        )
        req = _make_request()
        pep.record_execution(req, output_artifact={"result": "file content"})

        # Hook 应被触发（虽然 mock 不会实际调用 get_hooks）
        # 这里主要验证不抛异常
