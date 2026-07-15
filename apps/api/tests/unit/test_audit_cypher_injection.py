"""R-P0-007 regression tests: Cypher injection in audit_graphiti_channel.

Verifies that ``_query_with_neo4j`` uses parameterized Cypher queries
($param placeholders) and NEVER interpolates user-controlled fields
(``workspace_id``, ``trace_id``, ``actor_ids``, ``limit``) into the
Cypher string.

Companion fix: [audit_graphiti_channel.py](file:///e:/DEMO/AI/ontology-graphiti/odap/infra/security/audit_graphiti_channel.py)
sibling of R-P0-004 (which fixed the same class in ``audit_sqlite_channel``).
"""
import re
from unittest import mock

import pytest

from odap.infra.security.audit_graphiti_channel import GraphitiAuditChannel
from odap.infra.security.audit_models import AuditFilter


# ---------------------------------------------------------------------------
# Static / source-level guards
# ---------------------------------------------------------------------------

def test_no_fstring_user_input_in_cypher_string():
    """Static check: user-controlled fields MUST NOT appear inside f-strings
    that build Cypher queries.

    Scoped to ``_query_with_neo4j`` because that is the only function that
    builds a Cypher string. The companion ``_query_with_search`` builds a
    search-index query (not Cypher) and is checked separately.
    """
    import ast
    import inspect
    from pathlib import Path
    from odap.infra.security.audit_graphiti_channel import GraphitiAuditChannel

    # Extract the source segment of just the _query_with_neo4j function
    src_method = inspect.getsource(GraphitiAuditChannel._query_with_neo4j)

    forbidden_substrings = (
        "{filter.workspace_id}",
        "{filter.trace_id}",
        "{filter.limit}",
    )

    violations = []
    for needle in forbidden_substrings:
        if needle in src_method:
            violations.append(f"contains {needle!r}")
    assert not violations, (
        "User-controlled field interpolated into Cypher (forbidden by R-P0-007):\n  "
        + "\n  ".join(violations)
    )


def test_cypher_string_contains_dollar_param_placeholders():
    """After the fix, the method MUST use ``$param`` placeholders, not f-string."""
    import inspect
    from odap.infra.security.audit_graphiti_channel import GraphitiAuditChannel

    src = inspect.getsource(GraphitiAuditChannel._query_with_neo4j)
    # Must reference parameter placeholders
    assert "$ws" in src or "$workspace" in src, (
        "expected parameterized placeholder ($ws or $workspace) in _query_with_neo4j"
    )
    assert "$trace" in src or "$trace_id" in src, (
        "expected parameterized placeholder ($trace or $trace_id) in _query_with_neo4j"
    )
    assert "$limit" in src, "expected parameterized placeholder ($limit) in _query_with_neo4j"
    # Must NOT have f-string user interpolation (the previous bug)
    assert "f'\"{filter" not in src, "f-string with filter.x still present (Cypher injection)"
    assert 'f"\"{filter' not in src, 'f-string with filter.x still present (Cypher injection)'


# ---------------------------------------------------------------------------
# Behavioural tests (mock Neo4j session)
# ---------------------------------------------------------------------------

class _FakeNode:
    def __init__(self, props):
        self._props = props

    def __getitem__(self, key):
        return self._props.get(key)

    def keys(self):
        return self._props.keys()


def _build_channel():
    """Build a channel with a stubbed graph manager (no real Neo4j)."""
    gm = mock.MagicMock()
    gm.neo4j_driver.session.return_value.__enter__.return_value = mock.MagicMock()
    ch = GraphitiAuditChannel.__new__(GraphitiAuditChannel)
    ch._graph_manager = gm
    return ch, gm


@pytest.mark.asyncio
async def test_workspace_id_with_quote_passed_as_parameter():
    """A workspace_id containing a quote must be passed as a parameter, not inlined."""
    ch, gm = _build_channel()
    session = gm.neo4j_driver.session.return_value.__enter__.return_value
    session.run.return_value = []

    inj = 'ws1" OR MATCH (admin) DETACH DELETE admin //'
    flt = AuditFilter(workspace_id=inj, limit=10)
    await ch._query_with_neo4j(flt)

    # The Cypher passed to session.run MUST be a constant (no f-string interpolation)
    cypher, kwargs = session.run.call_args[0], session.run.call_args[1]
    assert len(cypher) == 1, "expected positional arg = single cypher string"
    cypher_str = cypher[0]
    assert inj not in cypher_str, (
        f"workspace_id inlined into Cypher (Cypher injection). cypher={cypher_str!r}"
    )
    # Must use $param placeholder
    assert "$" in cypher_str, f"expected $param placeholder. cypher={cypher_str!r}"
    # The inj string must be passed as a parameter kwarg
    assert inj in kwargs.values(), (
        f"workspace_id must be passed as parameter, not inlined. kwargs={kwargs!r}"
    )


@pytest.mark.asyncio
async def test_actor_ids_passed_as_list_parameter():
    """actor_ids must be passed as a list parameter, not f-string joined."""
    ch, gm = _build_channel()
    session = gm.neo4j_driver.session.return_value.__enter__.return_value
    session.run.return_value = []

    uids = ['u1"injection', 'u2) OR MATCH (admin) //']
    flt = AuditFilter(actor_ids=uids, limit=10)
    await ch._query_with_neo4j(flt)

    cypher_str = session.run.call_args[0][0]
    # actor_ids values must NOT appear inlined in the cypher
    for uid in uids:
        assert uid not in cypher_str, (
            f"actor_id {uid!r} inlined into Cypher (Cypher injection). cypher={cypher_str!r}"
        )
    # Must be passed as parameter
    kwargs = session.run.call_args[1]
    assert any(uids == v for v in kwargs.values()), (
        f"actor_ids must be passed as list parameter. kwargs={kwargs!r}"
    )


@pytest.mark.asyncio
async def test_limit_is_bounded():
    """A negative or huge limit must be clamped to [1, 1000]."""
    ch, gm = _build_channel()
    session = gm.neo4j_driver.session.return_value.__enter__.return_value
    session.run.return_value = []

    # Negative limit should be clamped
    flt = AuditFilter(limit=-5)
    await ch._query_with_neo4j(flt)
    bounded = session.run.call_args[1].get("limit")
    assert bounded is not None and 1 <= bounded <= 1000, (
        f"limit must be bounded to [1, 1000], got {bounded!r}"
    )

    # Huge limit should be clamped
    flt = AuditFilter(limit=10_000_000)
    await ch._query_with_neo4j(flt)
    bounded = session.run.call_args[1].get("limit")
    assert bounded is not None and bounded <= 1000, (
        f"limit must be bounded to [1, 1000], got {bounded!r}"
    )


@pytest.mark.asyncio
async def test_filter_with_no_constraints_still_safe():
    """An empty filter must not produce a Cypher with empty `WHERE TRUE` injection risk."""
    ch, gm = _build_channel()
    session = gm.neo4j_driver.session.return_value.__enter__.return_value
    session.run.return_value = []

    flt = AuditFilter()  # all None
    await ch._query_with_neo4j(flt)

    cypher_str = session.run.call_args[0][0]
    # Should not crash; should produce a safe query
    assert "MATCH (n:AuditLog)" in cypher_str
    assert "ORDER BY n.timestamp DESC" in cypher_str
    assert "LIMIT" in cypher_str
