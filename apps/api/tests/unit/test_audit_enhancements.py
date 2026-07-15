"""Unit tests for audit enhancements.

Covers:
- log_audit() new parameters (result_status, severity, duration_ms,
  workspace_id, result_message, details)
- audit_opa_decision() function
- Shared audit helper (audit, extract_user_id, extract_workspace_id)
- Audit middleware user extraction

Testing rules (AGENTS.md):
- SQLite storage tests use tmp_path for real DB (NOT MagicMock)
- Test files named test_{module}.py
- Use pytest
- Class organization: TestXxx grouped by layer
- Exception assertions: pytest.raises(ValueError, match="...")
"""
import json
import logging
import os
import sqlite3
import sys
import time
from unittest.mock import MagicMock, patch

import pytest

# Ensure project root is on sys.path
PROJECT_ROOT = os.path.dirname(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
)
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_real_sqlite_channel(tmp_path, name="audit_test.db"):
    """Create a real SQLiteAuditChannel backed by a tmp_path DB file.

    Per AGENTS.md: storage tests must use real DB (tmp_path), not MagicMock.
    """
    from odap.infra.security.audit_sqlite_channel import SQLiteAuditChannel

    db_path = str(tmp_path / name)
    return SQLiteAuditChannel(db_path=db_path)


def _query_audit_events(db_path):
    """Directly query the audit_events table to verify stored fields.

    Returns rows as dicts (newest first by insertion order).
    """
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM audit_events ORDER BY rowid DESC")
    rows = [dict(row) for row in cursor.fetchall()]
    conn.close()
    return rows


# ---------------------------------------------------------------------------
# TestLogAudit - test log_audit() with new parameters
# ---------------------------------------------------------------------------


class TestLogAudit:
    """Test log_audit() with new parameters (result_status, severity, etc.)."""

    @pytest.fixture
    def channel(self, tmp_path):
        """Real SQLiteAuditChannel with tmp_path DB."""
        return _make_real_sqlite_channel(tmp_path)

    def _call_log_audit(self, channel, **kwargs):
        """Call log_audit with patched channels (real SQLite, mock Graphiti).

        Mocking get_graphiti_channel avoids Graphiti dependencies; we are
        testing SQLite logic only.
        """
        from odap.infra.security import unified_audit

        with patch.object(unified_audit, "get_channel", return_value=channel), \
             patch.object(
                 unified_audit, "get_graphiti_channel", return_value=MagicMock()
             ):
            unified_audit.log_audit(**kwargs)

    def test_log_audit_with_result_status_success(self, channel):
        """result_status='success' produces INFO severity."""
        self._call_log_audit(
            channel,
            action="test_action",
            resource="test_resource",
            user="test_user",
            result_status="success",
        )
        rows = _query_audit_events(channel.db_path)
        assert len(rows) == 1
        assert rows[0]["severity"] == "info"

    def test_log_audit_with_result_status_failure(self, channel):
        """result_status='failure' produces ERROR severity."""
        self._call_log_audit(
            channel,
            action="test_action",
            resource="test_resource",
            user="test_user",
            result_status="failure",
        )
        rows = _query_audit_events(channel.db_path)
        assert len(rows) == 1
        assert rows[0]["severity"] == "error"

    def test_log_audit_with_result_status_denied(self, channel):
        """result_status='denied' produces WARN severity."""
        self._call_log_audit(
            channel,
            action="test_action",
            resource="test_resource",
            user="test_user",
            result_status="denied",
        )
        rows = _query_audit_events(channel.db_path)
        assert len(rows) == 1
        assert rows[0]["severity"] == "warn"

    def test_log_audit_with_explicit_severity(self, channel):
        """Explicit severity overrides inference from result_status."""
        # result_status='success' would infer 'info', but explicit 'warn' wins
        self._call_log_audit(
            channel,
            action="test_action",
            resource="test_resource",
            user="test_user",
            result_status="success",
            severity="warn",
        )
        rows = _query_audit_events(channel.db_path)
        assert len(rows) == 1
        assert rows[0]["severity"] == "warn"

    def test_log_audit_with_duration_ms(self, channel):
        """duration_ms is stored in the event."""
        self._call_log_audit(
            channel,
            action="test_action",
            resource="test_resource",
            user="test_user",
            duration_ms=1234,
        )
        rows = _query_audit_events(channel.db_path)
        assert len(rows) == 1
        assert rows[0]["duration_ms"] == 1234

    def test_log_audit_with_workspace_id(self, channel):
        """workspace_id is stored (not 'default')."""
        self._call_log_audit(
            channel,
            action="test_action",
            resource="test_resource",
            user="test_user",
            workspace_id="ws-custom-123",
        )
        rows = _query_audit_events(channel.db_path)
        assert len(rows) == 1
        assert rows[0]["workspace_id"] == "ws-custom-123"

    def test_log_audit_with_result_message(self, channel):
        """result_message is stored."""
        self._call_log_audit(
            channel,
            action="test_action",
            resource="test_resource",
            user="test_user",
            result_message="Operation completed successfully",
        )
        rows = _query_audit_events(channel.db_path)
        assert len(rows) == 1
        assert (
            rows[0]["result_message"] == "Operation completed successfully"
        )

    def test_log_audit_with_none_details(self, channel):
        """details=None doesn't crash (uses {})."""
        self._call_log_audit(
            channel,
            action="test_action",
            resource="test_resource",
            user="test_user",
            details=None,
        )
        rows = _query_audit_events(channel.db_path)
        assert len(rows) == 1
        # context should be an empty JSON object
        assert json.loads(rows[0]["context"]) == {}

    def test_log_audit_sqlite_write_failure_logged(self, caplog):
        """SQLite write failure logs warning (not silent)."""
        from odap.infra.security import unified_audit

        failing_channel = MagicMock()
        failing_channel.write_sync.side_effect = sqlite3.OperationalError(
            "disk full"
        )

        with patch.object(
            unified_audit, "get_channel", return_value=failing_channel
        ), patch.object(
            unified_audit, "get_graphiti_channel", return_value=MagicMock()
        ):
            with caplog.at_level(logging.WARNING, logger="audit"):
                unified_audit.log_audit(
                    action="test_action",
                    resource="test_resource",
                    user="test_user",
                )

        # Verify warning was logged (not silent)
        warning_messages = [
            r.message for r in caplog.records if r.levelno == logging.WARNING
        ]
        assert any(
            "SQLite audit write failed" in msg for msg in warning_messages
        )


# ---------------------------------------------------------------------------
# TestAuditOpaDecision - test audit_opa_decision()
# ---------------------------------------------------------------------------


class TestAuditOpaDecision:
    """Test audit_opa_decision() function."""

    @pytest.fixture
    def channel(self, tmp_path):
        """Real SQLiteAuditChannel with tmp_path DB."""
        return _make_real_sqlite_channel(tmp_path)

    def _call_audit_opa_decision(self, channel, **kwargs):
        """Call audit_opa_decision with patched channels."""
        from odap.infra.security import unified_audit

        with patch.object(unified_audit, "get_channel", return_value=channel), \
             patch.object(
                 unified_audit, "get_graphiti_channel", return_value=MagicMock()
             ):
            unified_audit.audit_opa_decision(**kwargs)

    def test_audit_opa_decision_allow(self, channel):
        """allow decision produces INFO severity."""
        self._call_audit_opa_decision(
            channel,
            subject="user1",
            action="read",
            resource="doc1",
            result="allow",
        )
        rows = _query_audit_events(channel.db_path)
        assert len(rows) == 1
        assert rows[0]["severity"] == "info"

    def test_audit_opa_decision_deny(self, channel):
        """deny decision produces WARN severity."""
        self._call_audit_opa_decision(
            channel,
            subject="user1",
            action="read",
            resource="doc1",
            result="deny",
        )
        rows = _query_audit_events(channel.db_path)
        assert len(rows) == 1
        assert rows[0]["severity"] == "warn"

    def test_audit_opa_decision_with_workspace_id(self, channel):
        """workspace_id is propagated (not hardcoded 'default')."""
        self._call_audit_opa_decision(
            channel,
            subject="user1",
            action="read",
            resource="doc1",
            result="allow",
            workspace_id="ws-opa-custom",
        )
        rows = _query_audit_events(channel.db_path)
        assert len(rows) == 1
        assert rows[0]["workspace_id"] == "ws-opa-custom"

    def test_audit_opa_decision_stores_policy_version(self, channel):
        """policy_version is stored in context."""
        self._call_audit_opa_decision(
            channel,
            subject="user1",
            action="read",
            resource="doc1",
            result="deny",
            policy_version="v1.2.3",
        )
        rows = _query_audit_events(channel.db_path)
        assert len(rows) == 1
        context = json.loads(rows[0]["context"])
        assert context["policy_version"] == "v1.2.3"


# ---------------------------------------------------------------------------
# TestAuditHelper - test the shared audit helper
# ---------------------------------------------------------------------------


class TestAuditHelper:
    """Test the shared audit helper (audit, extract_user_id, extract_workspace_id)."""

    def test_audit_helper_success(self):
        """audit() calls log_audit with correct params."""
        from odap.infra.security.audit_helper import audit

        with patch("odap.infra.security.unified_audit.log_audit") as mock_log_audit:
            audit(
                action="test_action",
                user="test_user",
                result_status="success",
                result_message="OK",
                details={"key": "value"},
                service="test_service",
                workspace_id="ws-test",
                resource="test_resource",
                duration_ms=100,
            )
            mock_log_audit.assert_called_once_with(
                action="test_action",
                resource="test_resource",
                user="test_user",
                service="test_service",
                result_status="success",
                result_message="OK",
                details={"key": "value"},
                workspace_id="ws-test",
                duration_ms=100,
            )

    def test_audit_helper_exception_not_raised(self):
        """audit() doesn't raise on log_audit failure."""
        from odap.infra.security.audit_helper import audit

        with patch(
            "odap.infra.security.unified_audit.log_audit",
            side_effect=Exception("DB error"),
        ):
            # Should not raise - audit() swallows and logs
            audit(
                action="test_action",
                user="test_user",
                result_status="success",
            )

    def test_audit_helper_exception_logged(self, caplog):
        """audit() logs warning on failure (not silent pass)."""
        from odap.infra.security.audit_helper import audit

        with patch(
            "odap.infra.security.unified_audit.log_audit",
            side_effect=Exception("DB error"),
        ):
            with caplog.at_level(logging.WARNING, logger="audit_helper"):
                audit(
                    action="test_action",
                    user="test_user",
                    result_status="success",
                    service="test_service",
                )

        warning_messages = [
            r.message for r in caplog.records if r.levelno == logging.WARNING
        ]
        assert any("Audit write failed" in msg for msg in warning_messages)

    def test_extract_user_id_from_dict(self):
        """extract_user_id extracts 'sub' from dict."""
        from odap.infra.security.audit_helper import extract_user_id

        assert extract_user_id({"sub": "user123"}) == "user123"

    def test_extract_user_id_from_none(self):
        """extract_user_id returns 'anonymous' for non-dict."""
        from odap.infra.security.audit_helper import extract_user_id

        assert extract_user_id(None) == "anonymous"

    def test_extract_workspace_id_from_dict(self):
        """extract_workspace_id extracts 'ws_id' from dict."""
        from odap.infra.security.audit_helper import extract_workspace_id

        assert extract_workspace_id({"ws_id": "ws-123"}) == "ws-123"

    def test_extract_workspace_id_default(self):
        """extract_workspace_id returns 'default' when ws_id missing."""
        from odap.infra.security.audit_helper import extract_workspace_id

        assert extract_workspace_id({"sub": "user1"}) == "default"


# ---------------------------------------------------------------------------
# TestAuditMiddleware - test middleware user extraction
# ---------------------------------------------------------------------------


class TestAuditMiddleware:
    """Test audit middleware user extraction."""

    def test_middleware_extracts_workspace_id(self):
        """middleware extracts ws_id from JWT."""
        from odap.infra.middleware.audit_middleware import (
            _extract_user_from_request,
        )
        import jwt as pyjwt
        from odap.infra.security.config import security_config

        token = pyjwt.encode(
            {
                "sub": "user123",
                "ws_id": "ws-custom",
                "exp": int(time.time()) + 3600,
            },
            security_config.get_jwt_secret(),
            algorithm=security_config.get_jwt_algorithm(),
        )

        mock_request = MagicMock()
        mock_request.headers = {"Authorization": f"Bearer {token}"}

        user_id, workspace_id = _extract_user_from_request(mock_request)
        assert workspace_id == "ws-custom"
        assert user_id == "user123"

    def test_middleware_expired_token_returns_anonymous(self):
        """expired token returns 'anonymous' (not original user)."""
        from odap.infra.middleware.audit_middleware import (
            _extract_user_from_request,
        )
        import jwt as pyjwt
        from odap.infra.security.config import security_config

        # Create an expired token with user info
        expired_token = pyjwt.encode(
            {
                "sub": "user123",
                "ws_id": "ws-custom",
                "exp": int(time.time()) - 3600,
            },
            security_config.get_jwt_secret(),
            algorithm=security_config.get_jwt_algorithm(),
        )

        mock_request = MagicMock()
        mock_request.headers = {"Authorization": f"Bearer {expired_token}"}

        user_id, workspace_id = _extract_user_from_request(mock_request)
        # Expired token should return "anonymous", not the original user
        assert user_id == "anonymous"
        assert workspace_id == "default"

    def test_middleware_no_auth_header_returns_anonymous(self):
        """missing Authorization header returns 'anonymous'."""
        from odap.infra.middleware.audit_middleware import (
            _extract_user_from_request,
        )

        mock_request = MagicMock()
        mock_request.headers = {}

        user_id, workspace_id = _extract_user_from_request(mock_request)
        assert user_id == "anonymous"
        assert workspace_id == "default"
