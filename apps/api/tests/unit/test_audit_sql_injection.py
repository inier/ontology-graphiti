"""
Regression test: SQL injection prevention in audit_sqlite_channel.

Tests for the `order_by` SQL injection vulnerability fix in R-P0-004.
The `order_by` field was previously user-controlled and directly interpolated
into a SQL string. Now it must be whitelisted.
"""
import pytest

from odap.infra.security.audit_sqlite_channel import (
    ALLOWED_ORDER_BY_COLUMNS,
    ORDER_BY_COLUMN_ALIASES,
    _resolve_order_by_column,
    SQLiteAuditChannel,
)


# ============ Whitelist unit tests ============

class TestOrderByWhitelist:
    def test_default_empty_returns_timestamp(self):
        assert _resolve_order_by_column("") == "timestamp"

    def test_none_returns_timestamp(self):
        assert _resolve_order_by_column(None) == "timestamp"  # type: ignore[arg-type]

    def test_valid_columns_accepted(self):
        for col in ALLOWED_ORDER_BY_COLUMNS:
            assert _resolve_order_by_column(col) == col

    def test_aliases_resolved(self):
        assert _resolve_order_by_column("time") == "timestamp"
        assert _resolve_order_by_column("actor") == "actor_id"
        assert _resolve_order_by_column("resource") == "resource_id"
        assert _resolve_order_by_column("event") == "event_type"

    def test_case_insensitive(self):
        assert _resolve_order_by_column("TIMESTAMP") == "timestamp"
        assert _resolve_order_by_column("Severity") == "severity"

    def test_injection_attempts_rejected(self):
        dangerous = [
            "timestamp; DROP TABLE audit_events; --",
            "1; DELETE FROM audit_events",
            "1 UNION SELECT password FROM users",
            "1 OR 1=1",
            "password",
            "secret_column",
            "*",
            "audit_events.*",
            "(SELECT 1)",
        ]
        for payload in dangerous:
            with pytest.raises(ValueError) as exc_info:
                _resolve_order_by_column(payload)
            assert "Invalid order_by column" in str(exc_info.value)

    def test_whitelist_is_frozen(self):
        # The whitelist must be a frozenset (immutable) to prevent runtime mutation
        assert isinstance(ALLOWED_ORDER_BY_COLUMNS, frozenset)
        with pytest.raises(AttributeError):
            ALLOWED_ORDER_BY_COLUMNS.add("malicious")  # type: ignore[attr-defined]


# ============ Integration test: full query path ============

class TestQueryInjectionPrevention:
    def _make_channel(self, tmp_path):
        db_path = str(tmp_path / "audit_test.db")
        ch = SQLiteAuditChannel(db_path=db_path)
        ch._init_db()
        return ch

    @pytest.mark.asyncio
    async def test_query_with_malicious_order_by_does_not_inject(self, tmp_path, caplog):
        """
        The full query path must NOT execute injection — either it raises
        ValueError (preferred) or returns an empty result. The malicious
        string must NEVER reach SQLite.
        """
        import logging
        ch = self._make_channel(tmp_path)
        from odap.infra.security.audit_models import AuditFilter
        malicious = "timestamp; DROP TABLE audit_events; --"
        f = AuditFilter(order_by=malicious, limit=10, offset=0)

        # Either:
        # (a) ValueError is raised (strict mode)
        # (b) Empty result is returned (resilient mode)
        # In both cases, the table must still exist afterwards
        try:
            with caplog.at_level(logging.WARNING):
                result = await ch.query(f)
            # If no exception: result must be empty (whitelist rejected it)
            assert result == []
        except ValueError as e:
            assert "Invalid order_by column" in str(e)

        # CRITICAL: the table must still exist
        result = await ch.query(AuditFilter(order_by="timestamp", limit=10, offset=0))
        assert isinstance(result, list)

    @pytest.mark.asyncio
    async def test_query_with_valid_order_by_succeeds(self, tmp_path):
        """The full query path must accept whitelisted order_by values."""
        ch = self._make_channel(tmp_path)
        from odap.infra.security.audit_models import AuditFilter
        for col in ["timestamp", "severity", "actor_id", "time", "actor"]:
            f = AuditFilter(order_by=col, order_desc=False, limit=10, offset=0)
            result = await ch.query(f)
            assert isinstance(result, list)

    @pytest.mark.asyncio
    async def test_table_still_exists_after_injection_attempt(self, tmp_path):
        """After a failed injection attempt, the table must still exist."""
        ch = self._make_channel(tmp_path)
        from odap.infra.security.audit_models import AuditFilter
        # First attempt injection (must not crash the table)
        await ch.query(AuditFilter(order_by="1; DROP TABLE audit_events", limit=10, offset=0))
        await ch.query(AuditFilter(order_by="timestamp; DROP TABLE audit_events; --", limit=10, offset=0))
        # Verify table still exists with a normal query
        result = await ch.query(AuditFilter(order_by="timestamp", limit=10, offset=0))
        assert isinstance(result, list)


# ============ Audit no other f-string SQL sites ============

class TestNoUnsafeSqlPatterns:
    def test_order_by_routed_through_safe_resolver(self):
        """
        The query method must route `filter.order_by` through the safe resolver
        before it reaches any SQL string. This is verified by:
        1. The variable `safe_order_by` is used in the SQL (not `filter.order_by`)
        2. The unsafe filter.order_by does not appear inside an f-string
        """
        import inspect
        from odap.infra.security.audit_sqlite_channel import SQLiteAuditChannel
        source = inspect.getsource(SQLiteAuditChannel.query)

        # The SQL must use safe_order_by
        assert "safe_order_by" in source, "Expected safe_order_by variable in query SQL"

        # The original filter.order_by must NOT appear in any f-string SQL
        # (because that's how injection happens)
        # Find all f-strings in the query method body
        import re
        fstrings = re.findall(r"f['\"][^'\"]*['\"]", source)
        for fs in fstrings:
            assert "filter.order_by" not in fs, (
                f"filter.order_by found inside f-string SQL: {fs!r}. "
                f"This is a SQL injection vector."
            )

    def test_no_fstring_user_input_in_sql(self):
        """Audit query() should not have any f-string SQL with user input."""
        import inspect
        from odap.infra.security.audit_sqlite_channel import SQLiteAuditChannel
        source = inspect.getsource(SQLiteAuditChannel.query)
        # f-string SQL is acceptable only with whitelisted/safe values
        # We allow it but verify the column passed in is whitelisted
        # (the f-string should reference safe_order_by, not filter.order_by)
        assert "safe_order_by" in source, "Expected safe_order_by variable usage"
