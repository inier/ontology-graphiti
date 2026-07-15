"""T083/T084 [TDD] Pattern discovery & completeness check tool tests.

Tests for AI pattern discovery (common attributes, foreign key patterns)
and completeness check (orphan types, missing audit fields, missing status).
"""
import pytest


@pytest.fixture
def object_types_basic():
    """3 object types with some common attributes and FK patterns."""
    return [
        {
            "type_id": "type-user",
            "name": "user",
            "display_name": "用户",
            "properties": [
                {"name": "email", "property_type": "STRING"},
                {"name": "phone", "property_type": "STRING"},
                {"name": "created_at", "property_type": "DATETIME"},
                {"name": "updated_at", "property_type": "DATETIME"},
            ],
        },
        {
            "type_id": "type-order",
            "name": "order",
            "display_name": "订单",
            "properties": [
                {"name": "total_amount", "property_type": "FLOAT"},
                {"name": "user_id", "property_type": "STRING"},
                {"name": "created_at", "property_type": "DATETIME"},
                {"name": "updated_at", "property_type": "DATETIME"},
            ],
        },
        {
            "type_id": "type-product",
            "name": "product",
            "display_name": "商品",
            "properties": [
                {"name": "name", "property_type": "STRING"},
                {"name": "price", "property_type": "FLOAT"},
                {"name": "created_at", "property_type": "DATETIME"},
            ],
        },
    ]


@pytest.fixture
def link_types_basic():
    return [
        {"link_id": "link-1", "name": "places", "source_type": "type-user", "target_type": "type-order"},
    ]


@pytest.fixture
def object_types_with_issues():
    """Object types with completeness issues: orphan, missing audit, missing status."""
    return [
        {
            "type_id": "type-user",
            "name": "user",
            "display_name": "用户",
            "description": "平台用户",
            "properties": [
                {"name": "email", "property_type": "STRING"},
                {"name": "phone", "property_type": "STRING"},
                {"name": "created_at", "property_type": "DATETIME"},
                {"name": "updated_at", "property_type": "DATETIME"},
            ],
        },
        {
            "type_id": "type-order",
            "name": "order",
            "display_name": "订单",
            "description": "",
            "properties": [
                {"name": "total_amount", "property_type": "FLOAT"},
                {"name": "user_id", "property_type": "STRING"},
            ],
        },
        {
            "type_id": "type-category",
            "name": "category",
            "display_name": "分类",
            "description": "商品分类",
            "properties": [
                {"name": "name", "property_type": "STRING"},
            ],
        },
    ]


# ── T083: Pattern Discovery ──────────────────────────────────────────

class TestPatternDiscoveryCommonAttributes:
    def test_detects_common_attributes_across_types(self, object_types_basic):
        from odap.biz.core.ontology.assistant.tools.pattern_discovery import (
            pattern_discovery,
        )
        result = pattern_discovery(
            ontology_id="ont-001",
            object_types=object_types_basic,
            link_types=[],
        )
        assert result["status"] == "ok"
        assert result["tool"] == "pattern_discovery"
        assert result["hitl_required"] is False
        common = result["common_attributes"]
        # created_at appears in all 3 types
        created_at_entry = next(c for c in common if c["name"] == "created_at")
        assert created_at_entry["count"] == 3
        assert "type-user" in created_at_entry["types"]
        assert "type-order" in created_at_entry["types"]
        assert "type-product" in created_at_entry["types"]
        assert "suggest_base_type" in created_at_entry["suggestion"]

    def test_no_common_attributes_returns_empty(self):
        from odap.biz.core.ontology.assistant.tools.pattern_discovery import (
            pattern_discovery,
        )
        object_types = [
            {"type_id": "a", "name": "a", "properties": [{"name": "x"}]},
            {"type_id": "b", "name": "b", "properties": [{"name": "y"}]},
        ]
        result = pattern_discovery("ont-001", object_types, [])
        assert result["common_attributes"] == []

    def test_common_attributes_threshold(self):
        """Attributes appearing in only 1 type should not be common."""
        from odap.biz.core.ontology.assistant.tools.pattern_discovery import (
            pattern_discovery,
        )
        object_types = [
            {"type_id": "a", "name": "a", "properties": [{"name": "unique_a"}]},
            {"type_id": "b", "name": "b", "properties": [{"name": "unique_a"}, {"name": "unique_b"}]},
        ]
        result = pattern_discovery("ont-001", object_types, [])
        names = [c["name"] for c in result["common_attributes"]]
        assert "unique_a" in names  # appears in 2 types
        assert "unique_b" not in names  # appears in only 1


class TestPatternDiscoveryForeignKey:
    def test_detects_foreign_key_pattern(self, object_types_basic):
        from odap.biz.core.ontology.assistant.tools.pattern_discovery import (
            pattern_discovery,
        )
        result = pattern_discovery(
            ontology_id="ont-001",
            object_types=object_types_basic,
            link_types=[],
        )
        fk_patterns = result["foreign_key_patterns"]
        # order has user_id, and "user" type exists
        fk = next(f for f in fk_patterns if f["property_name"] == "user_id")
        assert fk["source_type"] == "type-order"
        assert fk["target_type"] == "type-user"
        assert fk["target_type_name"] == "user"
        assert "suggest_relationship" in fk["suggestion"]

    def test_no_foreign_key_when_no_matching_type(self):
        from odap.biz.core.ontology.assistant.tools.pattern_discovery import (
            pattern_discovery,
        )
        object_types = [
            {"type_id": "a", "name": "alpha", "properties": [{"name": "beta_id"}]},
        ]
        result = pattern_discovery("ont-001", object_types, [])
        # beta_id doesn't match any type name "alpha"
        assert result["foreign_key_patterns"] == []

    def test_foreign_key_already_has_link_not_suggested(self, object_types_basic, link_types_basic):
        """If a link already exists between the types, note it as existing."""
        from odap.biz.core.ontology.assistant.tools.pattern_discovery import (
            pattern_discovery,
        )
        result = pattern_discovery(
            ontology_id="ont-001",
            object_types=object_types_basic,
            link_types=link_types_basic,
        )
        fk_patterns = result["foreign_key_patterns"]
        fk = next(f for f in fk_patterns if f["property_name"] == "user_id")
        assert fk.get("existing_link") is True


class TestPatternDiscoveryEmpty:
    def test_empty_object_types(self):
        from odap.biz.core.ontology.assistant.tools.pattern_discovery import (
            pattern_discovery,
        )
        result = pattern_discovery("ont-001", [], [])
        assert result["status"] == "ok"
        assert result["common_attributes"] == []
        assert result["foreign_key_patterns"] == []
        assert result["summary"]["total_object_types"] == 0


# ── T084: Completeness Check ─────────────────────────────────────────

class TestCompletenessCheckOrphanTypes:
    def test_detects_orphan_type(self, object_types_with_issues):
        from odap.biz.core.ontology.assistant.tools.completeness_check import (
            completeness_check,
        )
        # No links at all → all types are orphans
        result = completeness_check(
            ontology_id="ont-001",
            object_types=object_types_with_issues,
            link_types=[],
            action_types=[],
        )
        assert result["status"] == "ok"
        assert result["tool"] == "completeness_check"
        assert result["hitl_required"] is False
        orphans = result["orphan_types"]
        orphan_ids = [o["type_id"] for o in orphans]
        assert "type-category" in orphan_ids
        assert "type-user" in orphan_ids
        assert "type-order" in orphan_ids

    def test_no_orphans_when_all_connected(self, object_types_with_issues):
        from odap.biz.core.ontology.assistant.tools.completeness_check import (
            completeness_check,
        )
        link_types = [
            {"source_type": "type-user", "target_type": "type-order"},
            {"source_type": "type-order", "target_type": "type-category"},
        ]
        result = completeness_check(
            "ont-001", object_types_with_issues, link_types, []
        )
        assert result["orphan_types"] == []


class TestCompletenessCheckAuditFields:
    def test_detects_missing_audit_fields(self, object_types_with_issues):
        from odap.biz.core.ontology.assistant.tools.completeness_check import (
            completeness_check,
        )
        result = completeness_check(
            "ont-001", object_types_with_issues, [], []
        )
        missing_audit = result["missing_audit_fields"]
        # order is missing created_at and updated_at
        order_issue = next(m for m in missing_audit if m["type_id"] == "type-order")
        assert "created_at" in order_issue["missing"]
        assert "updated_at" in order_issue["missing"]
        # category is missing created_at and updated_at
        cat_issue = next(m for m in missing_audit if m["type_id"] == "type-category")
        assert "created_at" in cat_issue["missing"]
        assert "updated_at" in cat_issue["missing"]
        # user has both → not in list
        user_issues = [m for m in missing_audit if m["type_id"] == "type-user"]
        assert len(user_issues) == 0


class TestCompletenessCheckMissingStatus:
    def test_detects_missing_status_for_order(self, object_types_with_issues):
        from odap.biz.core.ontology.assistant.tools.completeness_check import (
            completeness_check,
        )
        result = completeness_check(
            "ont-001", object_types_with_issues, [], []
        )
        missing_status = result["missing_status"]
        # order should have status but doesn't
        order_issue = next(m for m in missing_status if m["type_id"] == "type-order")
        assert order_issue["suggested_field"] == "status"
        assert "order" in order_issue["type_name"]

    def test_no_missing_status_for_user(self, object_types_with_issues):
        from odap.biz.core.ontology.assistant.tools.completeness_check import (
            completeness_check,
        )
        result = completeness_check(
            "ont-001", object_types_with_issues, [], []
        )
        missing_status = result["missing_status"]
        # user doesn't typically need status
        user_issues = [m for m in missing_status if m["type_id"] == "type-user"]
        assert len(user_issues) == 0


class TestCompletenessCheckMissingDescription:
    def test_detects_empty_description(self, object_types_with_issues):
        from odap.biz.core.ontology.assistant.tools.completeness_check import (
            completeness_check,
        )
        result = completeness_check(
            "ont-001", object_types_with_issues, [], []
        )
        missing_desc = result["missing_description"]
        # order has empty description
        order_issue = next(m for m in missing_desc if m["type_id"] == "type-order")
        assert order_issue["type_name"] == "order"


class TestCompletenessCheckSummary:
    def test_summary_counts(self, object_types_with_issues):
        from odap.biz.core.ontology.assistant.tools.completeness_check import (
            completeness_check,
        )
        result = completeness_check(
            "ont-001", object_types_with_issues, [], []
        )
        summary = result["summary"]
        assert summary["total_object_types"] == 3
        assert summary["orphan_count"] == 3
        assert summary["missing_audit_count"] == 2  # order + category
        assert summary["missing_status_count"] == 1  # order
        assert summary["missing_description_count"] == 1  # order

    def test_empty_ontology(self):
        from odap.biz.core.ontology.assistant.tools.completeness_check import (
            completeness_check,
        )
        result = completeness_check("ont-001", [], [], [])
        assert result["status"] == "ok"
        assert result["orphan_types"] == []
        assert result["missing_audit_fields"] == []
        assert result["summary"]["total_object_types"] == 0
