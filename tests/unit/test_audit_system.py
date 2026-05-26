import pytest
import sys
import os
import sqlite3
from unittest.mock import MagicMock, patch, AsyncMock
from datetime import datetime

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..', '..'))

from odap.infra.security.unified_audit import _infer_event_type, log_audit, get_audit_logs
from odap.infra.security.audit_models import AuditEventType, AuditSeverity, AuditFilter
from odap.infra.security.audit_sqlite_channel import SQLiteAuditChannel
from odap.infra.middleware.audit_middleware import AuditMiddleware, _EXCLUDED_PATHS, _EXCLUDED_PREFIXES


class TestInferEventType:

    def test_ingest_action(self):
        assert _infer_event_type("ingest_data", "ingest") == AuditEventType.DATA_INGEST

    def test_ingest_service(self):
        assert _infer_event_type("create", "ingest") == AuditEventType.DATA_INGEST

    def test_query_action(self):
        assert _infer_event_type("query_executed", "query") == AuditEventType.QUERY

    def test_workspace_create(self):
        assert _infer_event_type("workspace_create", "workspace") == AuditEventType.WORKSPACE_CREATE

    def test_workspace_delete(self):
        assert _infer_event_type("workspace_delete", "workspace") == AuditEventType.WORKSPACE_DELETE

    def test_workspace_switch(self):
        assert _infer_event_type("workspace_switch", "workspace") == AuditEventType.WORKSPACE_SWITCH

    def test_ontology_create(self):
        assert _infer_event_type("ontology_create", "system") == AuditEventType.ONTOLOGY_CREATE

    def test_ontology_version(self):
        assert _infer_event_type("ontology_version", "system") == AuditEventType.ONTOLOGY_VERSION

    def test_ontology_rollback(self):
        assert _infer_event_type("ontology_rollback", "system") == AuditEventType.ONTOLOGY_ROLLBACK

    def test_pipeline_action(self):
        assert _infer_event_type("pipeline.build.completed", "system") == AuditEventType.ONTOLOGY_VERSION

    def test_login(self):
        assert _infer_event_type("user_login", "auth") == AuditEventType.USER_LOGIN

    def test_logout(self):
        assert _infer_event_type("user_logout", "auth") == AuditEventType.USER_LOGOUT

    def test_error(self):
        assert _infer_event_type("error_occurred", "system") == AuditEventType.SYSTEM_ERROR

    def test_skill(self):
        assert _infer_event_type("skill_execute", "skill") == AuditEventType.SKILL_EXECUTE

    def test_agent(self):
        assert _infer_event_type("agent_execute", "agent") == AuditEventType.AGENT_EXECUTE

    def test_policy(self):
        assert _infer_event_type("policy_change", "opa") == AuditEventType.POLICY_UPDATE

    def test_hook(self):
        assert _infer_event_type("hook_alert", "hook") == AuditEventType.SYSTEM_CONFIG

    def test_fallback_system_health(self):
        assert _infer_event_type("unknown_action", "unknown_service") == AuditEventType.SYSTEM_HEALTH

    def test_empty_action(self):
        assert _infer_event_type("", "") == AuditEventType.SYSTEM_HEALTH

    def test_none_action(self):
        assert _infer_event_type(None, None) == AuditEventType.SYSTEM_HEALTH


class TestSeverityAliases:

    def test_warning_alias(self):
        from odap.infra.security.audit_api import _normalize_severity
        assert _normalize_severity("warning") == "warn"

    def test_warn_direct(self):
        from odap.infra.security.audit_api import _normalize_severity
        assert _normalize_severity("warn") == "warn"

    def test_info_direct(self):
        from odap.infra.security.audit_api import _normalize_severity
        assert _normalize_severity("info") == "info"

    def test_error_direct(self):
        from odap.infra.security.audit_api import _normalize_severity
        assert _normalize_severity("error") == "error"

    def test_critical_direct(self):
        from odap.infra.security.audit_api import _normalize_severity
        assert _normalize_severity("critical") == "critical"

    def test_case_insensitive(self):
        from odap.infra.security.audit_api import _normalize_severity
        assert _normalize_severity("WARNING") == "warn"
        assert _normalize_severity("Info") == "info"

    def test_unknown_pass_through(self):
        from odap.infra.security.audit_api import _normalize_severity
        assert _normalize_severity("unknown") == "unknown"


class TestEventTypeAliases:

    def test_system_startup_alias(self):
        from odap.infra.security.audit_api import _normalize_event_type
        assert _normalize_event_type("system.startup") == "system.health"

    def test_system_shutdown_alias(self):
        from odap.infra.security.audit_api import _normalize_event_type
        assert _normalize_event_type("system.shutdown") == "system.health"

    def test_system_action_alias(self):
        from odap.infra.security.audit_api import _normalize_event_type
        assert _normalize_event_type("system.action") == "system.health"

    def test_workspace_update_alias(self):
        from odap.infra.security.audit_api import _normalize_event_type
        assert _normalize_event_type("workspace.update") == "workspace.create"

    def test_known_type_pass_through(self):
        from odap.infra.security.audit_api import _normalize_event_type
        assert _normalize_event_type("user.login") == "user.login"

    def test_unknown_type_pass_through(self):
        from odap.infra.security.audit_api import _normalize_event_type
        assert _normalize_event_type("custom.event") == "custom.event"


class TestAuditMiddlewareExcludedPaths:

    def test_docs_excluded(self):
        assert "/docs" in _EXCLUDED_PATHS

    def test_health_excluded(self):
        assert "/health" in _EXCLUDED_PATHS

    def test_openapi_excluded(self):
        assert "/openapi.json" in _EXCLUDED_PATHS

    def test_audit_api_excluded(self):
        assert "/api/audit" in _EXCLUDED_PREFIXES

    def test_static_excluded(self):
        assert "/static" in _EXCLUDED_PREFIXES


class TestAuditAPISQLiteIntegration:

    @pytest.fixture
    def channel(self, tmp_path):
        db_path = str(tmp_path / "test_audit.db")
        ch = SQLiteAuditChannel(db_path=db_path)
        return ch

    def test_write_and_query(self, channel):
        from odap.infra.security.audit_models import AuditEvent, ActorInfo, ResourceInfo, ActionResult

        event = AuditEvent(
            id="test-001",
            timestamp=datetime.now(),
            event_type=AuditEventType.DATA_INGEST,
            severity=AuditSeverity.INFO,
            source="ingest",
            actor=ActorInfo(actor_type="user", actor_id="user1", actor_name="Test User"),
            action="ingest_data",
            resource=ResourceInfo(resource_type="file", resource_id="test.txt"),
            result=ActionResult(status="success", message="OK"),
            context={"filename": "test.txt"},
            workspace_id="default",
            trace_id="trace-001",
        )

        import asyncio
        asyncio.run(channel.write(event))
        asyncio.run(channel.flush())

        filter_obj = AuditFilter(limit=10, offset=0)
        events = asyncio.run(channel.query(filter_obj))

        assert len(events) == 1
        assert events[0].id == "test-001"
        assert events[0].event_type == AuditEventType.DATA_INGEST
        assert events[0].action == "ingest_data"

    def test_write_multiple_event_types(self, channel):
        from odap.infra.security.audit_models import AuditEvent, ActorInfo, ResourceInfo, ActionResult

        events_data = [
            ("ingest_data", AuditEventType.DATA_INGEST, "ingest"),
            ("query_executed", AuditEventType.QUERY, "query"),
            ("workspace_create", AuditEventType.WORKSPACE_CREATE, "workspace"),
            ("error_occurred", AuditEventType.SYSTEM_ERROR, "system"),
        ]

        import asyncio
        for i, (action, event_type, source) in enumerate(events_data):
            event = AuditEvent(
                id=f"test-{i:03d}",
                timestamp=datetime.now(),
                event_type=event_type,
                severity=AuditSeverity.INFO,
                source=source,
                actor=ActorInfo(actor_type="user", actor_id="user1", actor_name="Test User"),
                action=action,
                resource=ResourceInfo(resource_type="resource", resource_id="res1"),
                result=ActionResult(status="success", message="OK"),
                context={},
                workspace_id="default",
                trace_id=f"trace-{i:03d}",
            )
            asyncio.run(channel.write(event))

        asyncio.run(channel.flush())

        filter_obj = AuditFilter(limit=10, offset=0)
        events = asyncio.run(channel.query(filter_obj))

        assert len(events) == 4
        types = {e.event_type for e in events}
        assert AuditEventType.DATA_INGEST in types
        assert AuditEventType.QUERY in types
        assert AuditEventType.WORKSPACE_CREATE in types
        assert AuditEventType.SYSTEM_ERROR in types

    def test_stats(self, channel):
        from odap.infra.security.audit_models import AuditEvent, ActorInfo, ResourceInfo, ActionResult

        event = AuditEvent(
            id="stats-001",
            timestamp=datetime.now(),
            event_type=AuditEventType.DATA_INGEST,
            severity=AuditSeverity.INFO,
            source="ingest",
            actor=ActorInfo(actor_type="user", actor_id="user1", actor_name="Test User"),
            action="ingest_data",
            resource=ResourceInfo(resource_type="file", resource_id="test.txt"),
            result=ActionResult(status="success", message="OK"),
            context={},
            workspace_id="default",
            trace_id="trace-stats",
        )

        import asyncio
        asyncio.run(channel.write(event))
        asyncio.run(channel.flush())

        stats = channel.get_stats()
        assert stats["total"] == 1
        assert "info" in stats.get("by_severity", {})

    def test_query_by_event_type(self, channel):
        from odap.infra.security.audit_models import AuditEvent, ActorInfo, ResourceInfo, ActionResult

        import asyncio
        for i, et in enumerate([AuditEventType.DATA_INGEST, AuditEventType.QUERY, AuditEventType.DATA_INGEST]):
            event = AuditEvent(
                id=f"filter-{i:03d}",
                timestamp=datetime.now(),
                event_type=et,
                severity=AuditSeverity.INFO,
                source="test",
                actor=ActorInfo(actor_type="user", actor_id="user1", actor_name="Test User"),
                action="test_action",
                resource=ResourceInfo(resource_type="resource", resource_id="res1"),
                result=ActionResult(status="success", message="OK"),
                context={},
                workspace_id="default",
                trace_id=f"trace-filter-{i:03d}",
            )
            asyncio.run(channel.write(event))

        asyncio.run(channel.flush())

        filter_obj = AuditFilter(event_types=[AuditEventType.DATA_INGEST], limit=10, offset=0)
        events = asyncio.run(channel.query(filter_obj))

        assert len(events) == 2
        assert all(e.event_type == AuditEventType.DATA_INGEST for e in events)


class TestEventToFlatDict:

    def test_flat_dict_has_required_fields(self):
        from odap.infra.security.audit_api import _event_to_flat_dict
        from odap.infra.security.audit_models import AuditEvent, ActorInfo, ResourceInfo, ActionResult

        event = AuditEvent(
            id="flat-001",
            timestamp=datetime.now(),
            event_type=AuditEventType.USER_LOGIN,
            severity=AuditSeverity.INFO,
            source="auth",
            actor=ActorInfo(actor_type="user", actor_id="user1", actor_name="Test User"),
            action="user_login",
            resource=ResourceInfo(resource_type="auth", resource_id="session"),
            result=ActionResult(status="success", message="Login OK"),
            context={"ip": "127.0.0.1"},
            workspace_id="default",
            trace_id="trace-flat",
        )

        flat = _event_to_flat_dict(event)

        assert flat["id"] == "flat-001"
        assert flat["event_type"] == "user.login"
        assert flat["severity"] == "info"
        assert flat["actor_type"] == "user"
        assert flat["actor_id"] == "user1"
        assert flat["actor_name"] == "Test User"
        assert flat["resource_type"] == "auth"
        assert flat["resource_id"] == "session"
        assert flat["result_status"] == "success"
        assert flat["result_message"] == "Login OK"
        assert isinstance(flat["timestamp"], str)

    def test_flat_dict_no_nested_actor(self):
        from odap.infra.security.audit_api import _event_to_flat_dict
        from odap.infra.security.audit_models import AuditEvent, ActorInfo, ResourceInfo, ActionResult

        event = AuditEvent(
            id="flat-002",
            timestamp=datetime.now(),
            event_type=AuditEventType.SYSTEM_HEALTH,
            severity=AuditSeverity.INFO,
            source="system",
            actor=ActorInfo(actor_type="system", actor_id="system", actor_name="System"),
            action="health_check",
            resource=ResourceInfo(resource_type="system", resource_id="health"),
            result=ActionResult(status="success"),
        )

        flat = _event_to_flat_dict(event)

        assert "actor" not in flat
        assert "resource" not in flat
        assert "result" not in flat
        assert "actor_type" in flat
        assert "resource_type" in flat
        assert "result_status" in flat


class TestGetTotalCount:

    def test_count_empty_db(self, tmp_path):
        from odap.infra.security.audit_api import _get_total_count

        db_path = str(tmp_path / "count_test.db")
        ch = SQLiteAuditChannel(db_path=db_path)

        count = _get_total_count(ch, {})
        assert count == 0

    def test_count_with_events(self, tmp_path):
        from odap.infra.security.audit_api import _get_total_count
        from odap.infra.security.audit_models import AuditEvent, ActorInfo, ResourceInfo, ActionResult

        db_path = str(tmp_path / "count_test2.db")
        ch = SQLiteAuditChannel(db_path=db_path)

        import asyncio
        for i in range(5):
            event = AuditEvent(
                id=f"count-{i:03d}",
                timestamp=datetime.now(),
                event_type=AuditEventType.SYSTEM_HEALTH,
                severity=AuditSeverity.INFO,
                source="system",
                actor=ActorInfo(actor_type="system", actor_id="system", actor_name="System"),
                action="health_check",
                resource=ResourceInfo(resource_type="system", resource_id="health"),
                result=ActionResult(status="success"),
            )
            asyncio.run(ch.write(event))
        asyncio.run(ch.flush())

        count = _get_total_count(ch, {})
        assert count == 5

    def test_count_with_severity_filter(self, tmp_path):
        from odap.infra.security.audit_api import _get_total_count
        from odap.infra.security.audit_models import AuditEvent, ActorInfo, ResourceInfo, ActionResult

        db_path = str(tmp_path / "count_test3.db")
        ch = SQLiteAuditChannel(db_path=db_path)

        import asyncio
        for i, sev in enumerate([AuditSeverity.INFO, AuditSeverity.ERROR, AuditSeverity.INFO]):
            event = AuditEvent(
                id=f"sev-{i:03d}",
                timestamp=datetime.now(),
                event_type=AuditEventType.SYSTEM_HEALTH,
                severity=sev,
                source="system",
                actor=ActorInfo(actor_type="system", actor_id="system", actor_name="System"),
                action="test",
                resource=ResourceInfo(resource_type="system", resource_id="test"),
                result=ActionResult(status="success"),
            )
            asyncio.run(ch.write(event))
        asyncio.run(ch.flush())

        count = _get_total_count(ch, {"severities": [AuditSeverity.INFO]})
        assert count == 2
