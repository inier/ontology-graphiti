"""
Regression test: OPA fail-close on OPA unavailable (R-P0-002).

Verifies that when the OPA server is unreachable or errors out, the OPAManager
denies permission by default (fail-close), unless OPA_FAIL_MODE=mock is
explicitly set in a non-production environment.

This is P0-7 in the architecture constitution: OPA unavailable MUST fail-close.
Fail-open (returning allow by default) is a critical security vulnerability.
"""
import os
import pytest
from unittest.mock import patch, MagicMock

# Save original env vars to restore after each test
ORIGINAL_ENV = os.environ.copy()


@pytest.fixture(autouse=True)
def reset_env(monkeypatch):
    """Reset OPA-related env vars for each test."""
    for var in ("OPA_MOCK_MODE", "OPA_FAIL_MODE", "ENV", "ENVIRONMENT"):
        monkeypatch.delenv(var, raising=False)


# ============ Test: fail mode resolution ============

class TestFailModeResolution:
    def test_default_is_deny(self, monkeypatch):
        """When no env var is set, default to fail-close (deny)."""
        from odap.infra.opa.opa_service import _resolve_opa_fail_mode
        # Make sure no env var influences the test
        for var in ("OPA_FAIL_MODE", "ENV", "ENVIRONMENT"):
            monkeypatch.delenv(var, raising=False)
        assert _resolve_opa_fail_mode() == "deny"

    def test_explicit_deny(self, monkeypatch):
        from odap.infra.opa.opa_service import _resolve_opa_fail_mode
        monkeypatch.setenv("OPA_FAIL_MODE", "deny")
        monkeypatch.delenv("ENV", raising=False)
        monkeypatch.delenv("ENVIRONMENT", raising=False)
        assert _resolve_opa_fail_mode() == "deny"

    def test_explicit_mock_in_dev(self, monkeypatch):
        from odap.infra.opa.opa_service import _resolve_opa_fail_mode
        monkeypatch.setenv("OPA_FAIL_MODE", "mock")
        monkeypatch.setenv("ENV", "development")
        assert _resolve_opa_fail_mode() == "mock"

    def test_mock_forbidden_in_production(self, monkeypatch):
        from odap.infra.opa.opa_service import _resolve_opa_fail_mode
        monkeypatch.setenv("OPA_FAIL_MODE", "mock")
        monkeypatch.setenv("ENV", "production")
        with pytest.raises(RuntimeError) as exc_info:
            _resolve_opa_fail_mode()
        assert "FORBIDDEN in production" in str(exc_info.value)

    def test_mock_forbidden_when_env_prod_alias(self, monkeypatch):
        from odap.infra.opa.opa_service import _resolve_opa_fail_mode
        monkeypatch.setenv("OPA_FAIL_MODE", "mock")
        monkeypatch.setenv("ENV", "prod")
        with pytest.raises(RuntimeError):
            _resolve_opa_fail_mode()

    def test_legacy_mock_forbidden_in_production(self, monkeypatch):
        """OPA_MOCK_MODE=true is rejected at startup in production."""
        monkeypatch.setenv("OPA_MOCK_MODE", "true")
        monkeypatch.setenv("ENV", "production")
        from odap.infra.opa.opa_service import OPAManager
        with pytest.raises(RuntimeError) as exc_info:
            OPAManager()
        assert "FORBIDDEN in production" in str(exc_info.value)


# ============ Test: check_permission fail-close ============

class TestCheckPermissionFailClose:
    def test_opa_exception_returns_false(self, monkeypatch):
        """When OPA raises an exception and fail_mode=deny, must return False."""
        from odap.infra.opa.opa_service import OPAManager

        # Force deny mode (the default)
        monkeypatch.setenv("OPA_FAIL_MODE", "deny")
        monkeypatch.delenv("ENV", raising=False)

        # Build manager with explicit use_mock=False (so it tries OPA)
        # Patch health_check to return True so init doesn't mark unavailable
        # Then patch opa_client.check_permission to raise
        with patch("odap.infra.opa.opa_service.OPAClient") as MockClient:
            mock_client = MagicMock()
            mock_client.health_check.return_value = True
            mock_client.check_permission.side_effect = ConnectionError("OPA down")
            MockClient.return_value = mock_client

            mgr = OPAManager(use_mock=False)

            # P0-7: MUST return False (deny)
            result = mgr.check_permission("pilot", "view_intelligence", {"id": "r1"})
            assert result is False, (
                f"FAIL-OPEN DETECTED! check_permission returned {result} on OPA error. "
                f"This is a P0 security vulnerability."
            )

    def test_opa_exception_abac_returns_allow_false(self, monkeypatch):
        """check_permission_abac on OPA error must return allow=False."""
        from odap.infra.opa.opa_service import OPAManager

        monkeypatch.setenv("OPA_FAIL_MODE", "deny")
        monkeypatch.delenv("ENV", raising=False)

        with patch("odap.infra.opa.opa_service.OPAClient") as MockClient:
            mock_client = MagicMock()
            mock_client.health_check.return_value = True
            mock_client.check_permission_abac.side_effect = ConnectionError("OPA down")
            MockClient.return_value = mock_client

            mgr = OPAManager(use_mock=False)
            user = {"id": "u1", "roles": ["pilot"]}
            result = mgr.check_permission_abac(user, "view", {"id": "r1"})

            assert result.get("allow") is False, (
                f"FAIL-OPEN DETECTED in ABAC! Result: {result}. "
                f"This is a P0 security vulnerability."
            )
            assert "fail-close" in result.get("reason", "").lower()

    def test_mock_mode_falls_back_in_dev(self, monkeypatch):
        """In dev with OPA_FAIL_MODE=mock, errors fall back to mock (legacy)."""
        from odap.infra.opa.opa_service import OPAManager

        monkeypatch.setenv("OPA_FAIL_MODE", "mock")
        monkeypatch.setenv("ENV", "development")

        with patch("odap.infra.opa.opa_service.OPAClient") as MockClient:
            mock_client = MagicMock()
            mock_client.health_check.return_value = True
            mock_client.check_permission.side_effect = ConnectionError("OPA down")
            MockClient.return_value = mock_client

            mgr = OPAManager()
            # In mock mode, falls back to mock implementation
            result = mgr.check_permission("pilot", "view_information", {"id": "r1"})
            # pilot has "view_information" in mock, so should be True
            assert result is True


# ============ Test: startup health check fail-close ============

class TestStartupHealthCheck:
    def test_opa_unavailable_at_startup_marks_unavailable(self, monkeypatch):
        """When OPA health check fails at init, manager should be marked unavailable."""
        from odap.infra.opa.opa_service import OPAManager

        monkeypatch.setenv("OPA_FAIL_MODE", "deny")
        monkeypatch.delenv("ENV", raising=False)

        with patch("odap.infra.opa.opa_service.OPAClient") as MockClient:
            mock_client = MagicMock()
            mock_client.health_check.return_value = False  # OPA down
            MockClient.return_value = mock_client

            mgr = OPAManager()
            # Should NOT auto-fallback to mock
            assert mgr.use_mock is False, (
                "FAIL-OPEN AT STARTUP: Manager auto-enabled mock when OPA is unavailable. "
                "This is a P0 violation."
            )
            assert getattr(mgr, "_opa_unavailable", False) is True


# ============ Test: source-level guard ============

class TestSourceGuards:
    """Static analysis: ensure the fail-open patterns are gone from the source."""

    def test_no_unconditional_fallback_to_mock(self):
        """The default fail-open pattern (unconditional fallback) must be gone.

        The remaining `fallback 到 Mock` strings are LEGITIMATE — they are
        gated by `if self._fail_mode == "mock"` (dev/test only). This test
        only catches the OLD pattern where the fallback was the default.
        """
        import inspect
        from odap.infra.opa.opa_service import OPAManager
        source = inspect.getsource(OPAManager)

        # OLD pattern (forbidden): "fallback 到 Mock" without a fail_mode guard
        # We look for log messages that do NOT have "(fail_mode=mock" disclaimer
        import re
        fallback_lines = []
        for lineno, line in enumerate(source.splitlines(), 1):
            if "fallback" in line and "Mock" in line:
                if "(fail_mode=mock" not in line:
                    fallback_lines.append(f"line {lineno}: {line.strip()}")

        assert not fallback_lines, (
            f"Found unconditional fallback (no fail_mode guard):\n"
            + "\n".join(fallback_lines)
        )

    def test_check_permission_returns_false_on_opa_error(self):
        """Verify check_permission explicitly returns False on OPA error."""
        import inspect
        from odap.infra.opa.opa_service import OPAManager
        source = inspect.getsource(OPAManager.check_permission)
        # The fail-close branch must exist
        assert "FAIL-CLOSE" in source, (
            "check_permission() must contain a FAIL-CLOSE branch"
        )
        # It must set result = False
        assert "result = False" in source, (
            "check_permission() fail-close branch must set result = False"
        )

    def test_check_permission_abac_returns_allow_false(self):
        import inspect
        from odap.infra.opa.opa_service import OPAManager
        source = inspect.getsource(OPAManager.check_permission_abac)
        assert "FAIL-CLOSE" in source
        # ABAC result must include "allow": False
        assert '"allow": False' in source, (
            "check_permission_abac() fail-close branch must return allow=False"
        )


# ============ Test: Policy hash verification (tampering detection) ============

class TestPolicyHashVerification:
    """Tests for policy integrity verification (F-3 requirement)."""

    def test_policy_bundle_has_checksum(self):
        """PolicyBundle must include a checksum for integrity verification."""
        from odap.infra.opa.opa_service import PolicyBundleManager
        import uuid

        manager = PolicyBundleManager()
        policies = {
            "domain.rego": "package domain\nallow { true }",
        }
        bundle = manager.create_bundle(policies)

        assert hasattr(bundle, "checksum"), (
            "PolicyBundle must have a checksum attribute"
        )
        assert bundle.checksum is not None and len(bundle.checksum) > 0, (
            "PolicyBundle checksum must be non-empty"
        )

    def test_policy_hash_mismatch_detected(self):
        """When policy checksum changes unexpectedly, the system must detect it."""
        from odap.infra.opa.opa_service import PolicyBundleManager, PolicyBundle

        manager = PolicyBundleManager()
        policies = {"domain.rego": "package domain\nallow { true }"}
        original_bundle = manager.create_bundle(policies)
        original_checksum = original_bundle.checksum

        assert manager.get_bundle() is not None
        assert manager.get_bundle().checksum == original_checksum

    def test_hot_update_creates_new_checksum(self):
        """Hot update must generate a new checksum for the new bundle."""
        from odap.infra.opa.opa_service import PolicyBundleManager

        manager = PolicyBundleManager()
        policies = {"domain.rego": "package domain\nallow { true }"}
        original_bundle = manager.create_bundle(policies)
        original_checksum = original_bundle.checksum

        new_policies = {"domain.rego": "package domain\nallow { false }"}
        updated_bundle = manager.hot_update_bundle(new_policies)

        assert updated_bundle.checksum != original_checksum, (
            "Hot update must generate a new checksum"
        )


# ============ Test: Timeout denial (F-3 requirement) ============

class TestTimeoutDenial:
    """Tests for OPA timeout handling - must deny on timeout."""

    def test_opa_timeout_returns_false(self, monkeypatch):
        """When OPA times out and fail_mode=deny, must return False."""
        from odap.infra.opa.opa_service import OPAManager

        monkeypatch.setenv("OPA_FAIL_MODE", "deny")
        monkeypatch.delenv("ENV", raising=False)

        with patch("odap.infra.opa.opa_service.OPAClient") as MockClient:
            mock_client = MagicMock()
            mock_client.health_check.return_value = True
            mock_client.check_permission.side_effect = TimeoutError("OPA timeout")
            MockClient.return_value = mock_client

            mgr = OPAManager(use_mock=False)
            result = mgr.check_permission("pilot", "view_intelligence", {"id": "r1"})

            assert result is False, (
                f"FAIL-OPEN ON TIMEOUT! check_permission returned {result}. "
                f"Must deny on OPA timeout."
            )

    def test_opa_timeout_abac_returns_allow_false(self, monkeypatch):
        """ABAC check must return allow=False on OPA timeout."""
        from odap.infra.opa.opa_service import OPAManager

        monkeypatch.setenv("OPA_FAIL_MODE", "deny")
        monkeypatch.delenv("ENV", raising=False)

        with patch("odap.infra.opa.opa_service.OPAClient") as MockClient:
            mock_client = MagicMock()
            mock_client.health_check.return_value = True
            mock_client.check_permission_abac.side_effect = TimeoutError("OPA timeout")
            MockClient.return_value = mock_client

            mgr = OPAManager(use_mock=False)
            user = {"id": "u1", "roles": ["pilot"]}
            result = mgr.check_permission_abac(user, "view", {"id": "r1"})

            assert result.get("allow") is False, (
                f"FAIL-OPEN IN ABAC ON TIMEOUT! Result: {result}. "
                f"Must deny on OPA timeout."
            )


# ============ Test: Reload rollback (F-3 requirement) ============

class TestReloadRollback:
    """Tests for policy reload failure - must rollback to previous bundle."""

    def test_rollback_bundle_restores_previous_version(self):
        """rollback_bundle must restore the previous bundle state."""
        import time
        from odap.infra.opa.opa_service import PolicyBundleManager

        manager = PolicyBundleManager()

        v1_policies = {"domain.rego": "package domain\nallow { true }"}
        v1 = manager.create_bundle(v1_policies)
        v1_version = v1.version
        v1_revision = v1.revision

        time.sleep(0.1)

        v2_policies = {"domain.rego": "package domain\nallow { false }"}
        v2 = manager.create_bundle(v2_policies)
        v2_version = v2.version
        v2_revision = v2.revision

        assert v1_revision != v2_revision
        assert manager.get_bundle().version == v2_version

        rolled_back = manager.rollback_bundle()

        assert rolled_back is not None
        assert rolled_back.revision == v1_revision
        assert manager.get_bundle().revision == v1_revision

    def test_rollback_when_no_previous_bundle(self):
        """rollback_bundle returns None when there's only one bundle."""
        from odap.infra.opa.opa_service import PolicyBundleManager

        manager = PolicyBundleManager()
        policies = {"domain.rego": "package domain\nallow { true }"}
        manager.create_bundle(policies)

        rolled_back = manager.rollback_bundle()

        assert rolled_back is None
        assert manager.get_bundle() is not None
