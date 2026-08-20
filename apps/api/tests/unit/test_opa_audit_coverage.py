#!/usr/bin/env python3
"""P1-01/02: OPA 决策审计全路径覆盖测试

验证所有 OPA 决策路径（RBAC/ABAC/mock/缓存命中/fail-close）
均产生审计事件，且审计写入失败不再静默 pass。
"""

import pytest
from unittest.mock import patch, MagicMock


class TestOPAManagerAuditCoverage:
    """验证 OPAManager 的各 check 方法均写审计"""

    def _make_manager(self, use_mock=True):
        from odap.infra.opa.opa_service import OPAManager
        mgr = OPAManager(use_mock=use_mock)
        return mgr

    def test_rbac_mock_writes_audit(self):
        """P1-01: RBAC mock 路径写审计"""
        mgr = self._make_manager(use_mock=True)
        with patch("odap.infra.security.unified_audit.audit_opa_decision") as mock_audit:
            mgr.check_permission("pilot", "view_information", {"id": "R1", "type": "ToolSystem"})
            assert mock_audit.called
            call_kwargs = mock_audit.call_args
            assert call_kwargs.kwargs["subject"] == "pilot"
            assert call_kwargs.kwargs["action"] == "view_information"

    def test_rbac_cache_hit_writes_audit(self):
        """P1-01: 缓存命中也写审计（reason 含 cache_hit）"""
        mgr = self._make_manager(use_mock=True)
        # 第一次调用填充缓存
        mgr.check_permission("pilot", "view_information", {"id": "R1", "type": "ToolSystem"})
        # 第二次命中缓存
        with patch("odap.infra.security.unified_audit.audit_opa_decision") as mock_audit:
            mgr.check_permission("pilot", "view_information", {"id": "R1", "type": "ToolSystem"})
            assert mock_audit.called
            assert "cache_hit" in mock_audit.call_args.kwargs.get("reason", "")

    def test_abac_mock_writes_audit(self):
        """P1-01: ABAC mock 路径写审计"""
        mgr = self._make_manager(use_mock=True)
        user = {"id": "u1", "roles": ["director"], "attributes": {"clearance_level": "secret"}}
        with patch("odap.infra.security.unified_audit.audit_opa_decision") as mock_audit:
            mgr.check_permission_abac(user, "view_information", {"id": "R1", "type": "ToolSystem"})
            assert mock_audit.called
            assert mock_audit.call_args.kwargs["subject"] == "u1"

    def test_abac_cache_hit_writes_audit(self):
        """P1-01: ABAC 缓存命中也写审计"""
        mgr = self._make_manager(use_mock=True)
        user = {"id": "u2", "roles": ["director"], "attributes": {"clearance_level": "secret"}}
        # 第一次填充缓存
        mgr.check_permission_abac(user, "view_information", {"id": "R2", "type": "ToolSystem"})
        # 第二次命中缓存
        with patch("odap.infra.security.unified_audit.audit_opa_decision") as mock_audit:
            mgr.check_permission_abac(user, "view_information", {"id": "R2", "type": "ToolSystem"})
            assert mock_audit.called
            assert "cache_hit" in mock_audit.call_args.kwargs.get("reason", "")

    def test_package_mock_writes_audit(self):
        """P1-01: package 级 mock 路径写审计"""
        mgr = self._make_manager(use_mock=True)
        with patch("odap.infra.security.unified_audit.audit_opa_decision") as mock_audit:
            mgr.check_package_permission("data_collection", {"role": "admin", "action": "search"})
            assert mock_audit.called
            call_kwargs = mock_audit.call_args.kwargs
            assert call_kwargs["subject"] == "admin"
            assert call_kwargs["action"] == "search"

    def test_package_cache_hit_writes_audit(self):
        """P1-01: package 缓存命中也写审计"""
        mgr = self._make_manager(use_mock=True)
        opa_input = {"role": "admin", "action": "search"}
        # 第一次填充缓存
        mgr.check_package_permission("data_collection", opa_input)
        # 第二次命中缓存
        with patch("odap.infra.security.unified_audit.audit_opa_decision") as mock_audit:
            mgr.check_package_permission("data_collection", opa_input)
            assert mock_audit.called
            assert "cache_hit" in mock_audit.call_args.kwargs.get("reason", "")


class TestABACServiceAuditCoverage:
    """P1-01 漏点 2: ABACService.check_permission_abac 写审计"""

    def test_abac_service_writes_audit_allow(self):
        from odap.infra.opa.opa_service import ABACService
        service = ABACService()
        subject = {"user_id": "alice", "roles": ["system_admin"], "clearance_level": "public"}
        action = {"type": "view", "category": "general"}
        resource = {"type": "doc", "classification": "public", "workspace_id": "ws1"}

        with patch("odap.infra.security.unified_audit.audit_opa_decision") as mock_audit:
            result = service.check_permission_abac(subject, action, resource)
            assert mock_audit.called
            assert mock_audit.call_args.kwargs["subject"] == "alice"
            assert mock_audit.call_args.kwargs["result"] == "allow"

    def test_abac_service_writes_audit_deny(self):
        from odap.infra.opa.opa_service import ABACService
        service = ABACService()
        subject = {"user_id": "bob", "roles": ["guest"], "clearance_level": "public"}
        action = {"type": "view", "category": "general"}
        resource = {"type": "doc", "classification": "secret", "workspace_id": "ws1"}

        with patch("odap.infra.security.unified_audit.audit_opa_decision") as mock_audit:
            result = service.check_permission_abac(subject, action, resource)
            assert mock_audit.called
            assert mock_audit.call_args.kwargs["result"] == "deny"
            assert "clearance" in mock_audit.call_args.kwargs["reason"].lower()


class TestAuditFailureNotSilent:
    """P1-02: 审计写入失败不再静默 pass，应 logger.warning"""

    def test_audit_failure_logs_warning(self, caplog):
        """审计写入失败时 logger.warning 被调用"""
        import logging
        from odap.infra.opa.opa_service import OPAClient

        with patch("odap.infra.security.unified_audit.audit_opa_decision",
                   side_effect=RuntimeError("DB down")):
            with caplog.at_level(logging.WARNING):
                OPAClient._audit_decision("user1", "view", {"package": "test"}, True, "ok")
        # 验证有 warning 日志
        assert any("审计写入失败" in record.message for record in caplog.records)

    def test_abac_evaluator_audit_failure_logs_warning(self, caplog):
        """ABACPolicyEvaluator 审计失败时 logger.warning 被调用"""
        import logging
        from odap.infra.opa.opa_service import ABACPolicyEvaluator

        evaluator = ABACPolicyEvaluator()
        user = {"id": "u1", "roles": ["director"], "attributes": {"clearance_level": "secret"}}

        with patch("odap.infra.security.unified_audit.audit_opa_decision",
                   side_effect=RuntimeError("DB down")):
            with caplog.at_level(logging.WARNING):
                evaluator._audit_policy_decision(user, "view", {"type": "doc"}, {"allow": True})
        assert any("审计写入失败" in record.message for record in caplog.records)
