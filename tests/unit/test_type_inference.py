"""T057 [TDD] TypeInferenceEngine tests.

Tests for local rule engine that infers property data type from property name.
Covers: exact match, prefix match, suffix match, contains match, fallback,
constraint suggestions, and 40+ property name groups covering 90+ variants.
"""
import pytest


class TestExactMatch:
    """Exact property name → type mapping."""

    @pytest.mark.parametrize("name,expected_type", [
        ("id", "STRING"),
        ("name", "STRING"),
        ("title", "STRING"),
        ("description", "STRING"),
        ("email", "STRING"),
        ("phone", "STRING"),
        ("mobile", "STRING"),
        ("telephone", "STRING"),
        ("address", "STRING"),
        ("age", "INTEGER"),
        ("price", "FLOAT"),
        ("cost", "FLOAT"),
        ("fee", "FLOAT"),
        ("salary", "FLOAT"),
        ("amount", "FLOAT"),
        ("total", "FLOAT"),
        ("sum", "FLOAT"),
        ("quantity", "INTEGER"),
        ("count", "INTEGER"),
        ("stock", "INTEGER"),
        ("weight", "FLOAT"),
        ("height", "FLOAT"),
        ("width", "FLOAT"),
        ("length", "FLOAT"),
        ("status", "STRING"),
        ("type", "STRING"),
        ("category", "STRING"),
        ("created_at", "DATETIME"),
        ("created_time", "DATETIME"),
        ("updated_at", "DATETIME"),
        ("modified_at", "DATETIME"),
        ("deleted_at", "DATETIME"),
        ("is_active", "BOOLEAN"),
        ("is_enabled", "BOOLEAN"),
        ("is_deleted", "BOOLEAN"),
        ("is_valid", "BOOLEAN"),
        ("is_verified", "BOOLEAN"),
        ("is_locked", "BOOLEAN"),
        ("has_permission", "BOOLEAN"),
        ("has_access", "BOOLEAN"),
        ("password", "STRING"),
        ("secret", "STRING"),
        ("token", "STRING"),
        ("avatar", "STRING"),
        ("image", "STRING"),
        ("photo", "STRING"),
        ("icon", "STRING"),
        ("url", "STRING"),
        ("website", "STRING"),
        ("homepage", "STRING"),
        ("latitude", "FLOAT"),
        ("lat", "FLOAT"),
        ("longitude", "FLOAT"),
        ("lng", "FLOAT"),
        ("lon", "FLOAT"),
        ("score", "FLOAT"),
        ("rating", "FLOAT"),
        ("priority", "INTEGER"),
        ("level", "INTEGER"),
        ("order", "INTEGER"),
        ("code", "STRING"),
        ("code_name", "STRING"),
        ("version", "STRING"),
        ("duration", "INTEGER"),
        ("timeout", "INTEGER"),
        ("percentage", "FLOAT"),
        ("percent", "FLOAT"),
        ("ratio", "FLOAT"),
        ("ip", "STRING"),
        ("ip_address", "STRING"),
        ("color", "STRING"),
        ("colour", "STRING"),
        ("locale", "STRING"),
        ("language", "STRING"),
        ("timezone", "STRING"),
        ("currency", "STRING"),
        ("gender", "STRING"),
        ("sex", "STRING"),
        ("birthday", "DATETIME"),
        ("birth_date", "DATETIME"),
        ("start_date", "DATETIME"),
        ("end_date", "DATETIME"),
        ("parent_id", "REFERENCE"),
        ("owner_id", "REFERENCE"),
        ("creator_id", "REFERENCE"),
        ("metadata", "JSON"),
        ("extra_data", "JSON"),
        ("tags", "JSON"),
        ("labels", "JSON"),
        ("coordinates", "JSON"),
        ("geo_point", "GEOPOINT"),
        ("location", "GEOPOINT"),
    ])
    def test_exact_match_returns_expected_type(self, name, expected_type):
        from odap.biz.core.ontology.assistant.rules.type_inference import (
            TypeInferenceEngine,
        )
        engine = TypeInferenceEngine()
        result = engine.infer_type(name)
        assert result["inferred_type"] == expected_type
        assert result["source"] == "rule_engine"
        assert result["match_rule"] == "exact_match"
        assert result["confidence"] == 1.0


class TestPrefixMatch:
    """Prefix-based type inference."""

    @pytest.mark.parametrize("name,expected_type", [
        ("is_published", "BOOLEAN"),
        ("has_role", "BOOLEAN"),
        ("can_edit", "BOOLEAN"),
        ("is_approved", "BOOLEAN"),
        ("has_subscription", "BOOLEAN"),
    ])
    def test_prefix_match_returns_boolean(self, name, expected_type):
        from odap.biz.core.ontology.assistant.rules.type_inference import (
            TypeInferenceEngine,
        )
        engine = TypeInferenceEngine()
        result = engine.infer_type(name)
        assert result["inferred_type"] == expected_type
        assert result["match_rule"] == "prefix_match"


class TestSuffixMatch:
    """Suffix-based type inference."""

    @pytest.mark.parametrize("name,expected_type", [
        ("signup_at", "DATETIME"),
        ("event_date", "DATETIME"),
        ("login_time", "DATETIME"),
        ("user_id", "REFERENCE"),
        ("product_id", "REFERENCE"),
        ("item_count", "INTEGER"),
        ("row_num", "INTEGER"),
        ("page_number", "INTEGER"),
        ("unit_price", "FLOAT"),
        ("total_amount", "FLOAT"),
        ("tax_rate", "FLOAT"),
        ("aspect_ratio", "FLOAT"),
        ("full_name", "STRING"),
        ("book_title", "STRING"),
        ("warning_label", "STRING"),
        ("short_desc", "STRING"),
        ("long_description", "STRING"),
        ("avatar_url", "STRING"),
        ("resource_uri", "STRING"),
        ("page_link", "STRING"),
        ("file_path", "STRING"),
        ("settings_json", "JSON"),
        ("page_meta", "JSON"),
        ("app_config", "JSON"),
        ("raw_data", "JSON"),
        ("store_lat", "FLOAT"),
        ("office_lng", "FLOAT"),
        ("home_lon", "FLOAT"),
    ])
    def test_suffix_match_returns_expected_type(self, name, expected_type):
        from odap.biz.core.ontology.assistant.rules.type_inference import (
            TypeInferenceEngine,
        )
        engine = TypeInferenceEngine()
        result = engine.infer_type(name)
        assert result["inferred_type"] == expected_type
        assert result["match_rule"] == "suffix_match"


class TestContainsMatch:
    """Contains-based type inference."""

    @pytest.mark.parametrize("name,expected_type", [
        ("user_email_addr", "STRING"),
        ("contact_phone_no", "STRING"),
        ("shipping_address_line", "STRING"),
        ("site_url_ref", "STRING"),
        ("item_price_value", "FLOAT"),
        ("total_amount_due", "FLOAT"),
        ("service_cost_total", "FLOAT"),
        ("membership_fee_paid", "FLOAT"),
        ("monthly_salary_net", "FLOAT"),
        ("user_age_value", "INTEGER"),
        ("order_count_total", "INTEGER"),
        ("product_quantity_left", "INTEGER"),
        ("grand_total_sum", "INTEGER"),
        ("file_size_bytes", "INTEGER"),
        ("name_length_chars", "INTEGER"),
        ("order_date_placed", "DATETIME"),
        ("event_time_start", "DATETIME"),
        ("created_timestamp_log", "DATETIME"),
        ("feature_flag_set", "BOOLEAN"),
        ("auto_enabled_flag", "BOOLEAN"),
        ("user_active_flag", "BOOLEAN"),
        ("panel_visible_flag", "BOOLEAN"),
        ("soft_deleted_flag", "BOOLEAN"),
    ])
    def test_contains_match_returns_expected_type(self, name, expected_type):
        from odap.biz.core.ontology.assistant.rules.type_inference import (
            TypeInferenceEngine,
        )
        engine = TypeInferenceEngine()
        result = engine.infer_type(name)
        assert result["inferred_type"] == expected_type
        assert result["match_rule"] == "contains_match"


class TestFallbackAndEdgeCases:
    """Fallback behavior and edge cases."""

    def test_unknown_property_defaults_to_string(self):
        from odap.biz.core.ontology.assistant.rules.type_inference import (
            TypeInferenceEngine,
        )
        engine = TypeInferenceEngine()
        result = engine.infer_type("xyz_unknown_field")
        assert result["inferred_type"] == "STRING"
        assert result["match_rule"] == "fallback"
        assert result["confidence"] < 1.0

    def test_empty_string_defaults_to_string(self):
        from odap.biz.core.ontology.assistant.rules.type_inference import (
            TypeInferenceEngine,
        )
        engine = TypeInferenceEngine()
        result = engine.infer_type("")
        assert result["inferred_type"] == "STRING"

    def test_exact_match_takes_priority_over_suffix(self):
        from odap.biz.core.ontology.assistant.rules.type_inference import (
            TypeInferenceEngine,
        )
        engine = TypeInferenceEngine()
        result = engine.infer_type("created_at")
        assert result["match_rule"] == "exact_match"

    def test_exact_match_takes_priority_over_contains(self):
        from odap.biz.core.ontology.assistant.rules.type_inference import (
            TypeInferenceEngine,
        )
        engine = TypeInferenceEngine()
        result = engine.infer_type("is_active")
        assert result["match_rule"] == "exact_match"

    def test_suffix_match_takes_priority_over_contains(self):
        from odap.biz.core.ontology.assistant.rules.type_inference import (
            TypeInferenceEngine,
        )
        engine = TypeInferenceEngine()
        result = engine.infer_type("order_count")
        assert result["match_rule"] == "suffix_match"

    def test_case_insensitive_match(self):
        from odap.biz.core.ontology.assistant.rules.type_inference import (
            TypeInferenceEngine,
        )
        engine = TypeInferenceEngine()
        result = engine.infer_type("EMAIL")
        assert result["inferred_type"] == "STRING"
        assert result["match_rule"] == "exact_match"


class TestConstraintSuggestions:
    """Constraint suggestions bundled with type inference."""

    def test_email_gets_email_constraint(self):
        from odap.biz.core.ontology.assistant.rules.type_inference import (
            TypeInferenceEngine,
        )
        engine = TypeInferenceEngine()
        result = engine.infer_type("email")
        assert "suggested_constraints" in result
        constraints = result["suggested_constraints"]
        assert constraints is not None
        assert constraints.get("format") == "email" or "pattern" in constraints

    def test_age_gets_range_constraint(self):
        from odap.biz.core.ontology.assistant.rules.type_inference import (
            TypeInferenceEngine,
        )
        engine = TypeInferenceEngine()
        result = engine.infer_type("age")
        constraints = result.get("suggested_constraints") or {}
        assert constraints.get("minimum") == 0
        assert constraints.get("maximum") == 150

    def test_price_gets_min_constraint(self):
        from odap.biz.core.ontology.assistant.rules.type_inference import (
            TypeInferenceEngine,
        )
        engine = TypeInferenceEngine()
        result = engine.infer_type("price")
        constraints = result.get("suggested_constraints") or {}
        assert constraints.get("minimum") == 0

    def test_name_has_no_constraints(self):
        from odap.biz.core.ontology.assistant.rules.type_inference import (
            TypeInferenceEngine,
        )
        engine = TypeInferenceEngine()
        result = engine.infer_type("name")
        constraints = result.get("suggested_constraints")
        assert constraints is None or constraints == {}


class TestInferBatch:
    """Batch inference for multiple property names."""

    def test_infer_batch_returns_list(self):
        from odap.biz.core.ontology.assistant.rules.type_inference import (
            TypeInferenceEngine,
        )
        engine = TypeInferenceEngine()
        names = ["email", "age", "is_active", "created_at", "unknown_xyz"]
        results = engine.infer_batch(names)
        assert len(results) == 5
        assert results[0]["inferred_type"] == "STRING"
        assert results[1]["inferred_type"] == "INTEGER"
        assert results[2]["inferred_type"] == "BOOLEAN"
        assert results[3]["inferred_type"] == "DATETIME"
        assert results[4]["inferred_type"] == "STRING"

    def test_infer_batch_empty_list(self):
        from odap.biz.core.ontology.assistant.rules.type_inference import (
            TypeInferenceEngine,
        )
        engine = TypeInferenceEngine()
        results = engine.infer_batch([])
        assert results == []
