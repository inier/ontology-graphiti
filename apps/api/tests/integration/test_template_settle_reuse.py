"""DEPRECATED in Iter 2.1 (ADR-074): template settle/reuse integration tests.

The FR-017/FR-018 "settled template" persistence (YAML to disk + metadata
to SQLite he_templates table) has been removed. Application-layer template
sediment is superseded by the persistent HE Knowledge Abstract at
``data/he_kb/{workspace_id}/{ontology_id}/``.

Replacement coverage:
- KA persistence (feed_to_kb / load_from_kb): see tests/unit/test_he_kb_persistence.py
- assess() full pipeline (no settled short-circuit): see tests/unit/test_template_engine.py

This file is retained as a placeholder to document the migration. The
module-level skip ensures it never runs.
"""
import pytest

pytestmark = pytest.mark.skip(
    reason="DEPRECATED in Iter 2.1: FR-017/FR-018 settled-template "
           "persistence removed. See test_he_kb_persistence.py for KA tests."
)
