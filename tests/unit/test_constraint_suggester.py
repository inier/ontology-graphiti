"""T058 [TDD] ConstraintSuggester tests.

Tests for local rule engine that suggests validation constraints
based on property name and data type.
"""
import pytest


class TestEmailConstraints:
    def test_email_gets_email_format_constraint(self):
        from odap.biz.core.ontology.assistant.rules.constraint_suggester import (
            ConstraintSuggester,
        )
        suggester = ConstraintSuggester()
        result = suggester.suggest("email", "STRING")
        constraints = result["constraints"]
        assert constraints.get("format") == "email"
        assert "pattern" in constraints

    def test_user_email_gets_email_constraint(self):
        from odap.biz.core.ontology.assistant.rules.constraint_suggester import (
            ConstraintSuggester,
        )
        suggester = ConstraintSuggester()
        result = suggester.suggest("user_email", "STRING")
        constraints = result["constraints"]
        assert constraints.get("format") == "email"


class TestPhoneConstraints:
    def test_phone_gets_phone_pattern(self):
        from odap.biz.core.ontology.assistant.rules.constraint_suggester import (
            ConstraintSuggester,
        )
        suggester = ConstraintSuggester()
        result = suggester.suggest("phone", "STRING")
        constraints = result["constraints"]
        assert "pattern" in constraints

    def test_mobile_gets_phone_pattern(self):
        from odap.biz.core.ontology.assistant.rules.constraint_suggester import (
            ConstraintSuggester,
        )
        suggester = ConstraintSuggester()
        result = suggester.suggest("mobile", "STRING")
        constraints = result["constraints"]
        assert "pattern" in constraints


class TestUrlConstraints:
    def test_url_gets_uri_format(self):
        from odap.biz.core.ontology.assistant.rules.constraint_suggester import (
            ConstraintSuggester,
        )
        suggester = ConstraintSuggester()
        result = suggester.suggest("url", "STRING")
        constraints = result["constraints"]
        assert constraints.get("format") == "uri"

    def test_website_gets_uri_format(self):
        from odap.biz.core.ontology.assistant.rules.constraint_suggester import (
            ConstraintSuggester,
        )
        suggester = ConstraintSuggester()
        result = suggester.suggest("website", "STRING")
        constraints = result["constraints"]
        assert constraints.get("format") == "uri"


class TestNumericRangeConstraints:
    def test_age_gets_0_to_150(self):
        from odap.biz.core.ontology.assistant.rules.constraint_suggester import (
            ConstraintSuggester,
        )
        suggester = ConstraintSuggester()
        result = suggester.suggest("age", "INTEGER")
        constraints = result["constraints"]
        assert constraints.get("minimum") == 0
        assert constraints.get("maximum") == 150

    def test_price_gets_min_0(self):
        from odap.biz.core.ontology.assistant.rules.constraint_suggester import (
            ConstraintSuggester,
        )
        suggester = ConstraintSuggester()
        result = suggester.suggest("price", "FLOAT")
        constraints = result["constraints"]
        assert constraints.get("minimum") == 0

    def test_amount_gets_min_0(self):
        from odap.biz.core.ontology.assistant.rules.constraint_suggester import (
            ConstraintSuggester,
        )
        suggester = ConstraintSuggester()
        result = suggester.suggest("amount", "FLOAT")
        constraints = result["constraints"]
        assert constraints.get("minimum") == 0

    def test_cost_gets_min_0(self):
        from odap.biz.core.ontology.assistant.rules.constraint_suggester import (
            ConstraintSuggester,
        )
        suggester = ConstraintSuggester()
        result = suggester.suggest("cost", "FLOAT")
        constraints = result["constraints"]
        assert constraints.get("minimum") == 0

    def test_percentage_gets_0_to_100(self):
        from odap.biz.core.ontology.assistant.rules.constraint_suggester import (
            ConstraintSuggester,
        )
        suggester = ConstraintSuggester()
        result = suggester.suggest("percentage", "FLOAT")
        constraints = result["constraints"]
        assert constraints.get("minimum") == 0
        assert constraints.get("maximum") == 100

    def test_ratio_gets_0_to_100(self):
        from odap.biz.core.ontology.assistant.rules.constraint_suggester import (
            ConstraintSuggester,
        )
        suggester = ConstraintSuggester()
        result = suggester.suggest("ratio", "FLOAT")
        constraints = result["constraints"]
        assert constraints.get("minimum") == 0
        assert constraints.get("maximum") == 100


class TestGeoConstraints:
    def test_latitude_gets_minus90_to_90(self):
        from odap.biz.core.ontology.assistant.rules.constraint_suggester import (
            ConstraintSuggester,
        )
        suggester = ConstraintSuggester()
        result = suggester.suggest("latitude", "FLOAT")
        constraints = result["constraints"]
        assert constraints.get("minimum") == -90
        assert constraints.get("maximum") == 90

    def test_longitude_gets_minus180_to_180(self):
        from odap.biz.core.ontology.assistant.rules.constraint_suggester import (
            ConstraintSuggester,
        )
        suggester = ConstraintSuggester()
        result = suggester.suggest("longitude", "FLOAT")
        constraints = result["constraints"]
        assert constraints.get("minimum") == -180
        assert constraints.get("maximum") == 180


class TestPatternConstraints:
    def test_color_gets_hex_pattern(self):
        from odap.biz.core.ontology.assistant.rules.constraint_suggester import (
            ConstraintSuggester,
        )
        suggester = ConstraintSuggester()
        result = suggester.suggest("color", "STRING")
        constraints = result["constraints"]
        assert "pattern" in constraints

    def test_ip_gets_ipv4_pattern(self):
        from odap.biz.core.ontology.assistant.rules.constraint_suggester import (
            ConstraintSuggester,
        )
        suggester = ConstraintSuggester()
        result = suggester.suggest("ip", "STRING")
        constraints = result["constraints"]
        assert "pattern" in constraints


class TestNoConstraints:
    def test_name_has_no_constraints(self):
        from odap.biz.core.ontology.assistant.rules.constraint_suggester import (
            ConstraintSuggester,
        )
        suggester = ConstraintSuggester()
        result = suggester.suggest("name", "STRING")
        assert result["constraints"] == {}

    def test_description_has_no_constraints(self):
        from odap.biz.core.ontology.assistant.rules.constraint_suggester import (
            ConstraintSuggester,
        )
        suggester = ConstraintSuggester()
        result = suggester.suggest("description", "STRING")
        assert result["constraints"] == {}

    def test_unknown_property_has_no_constraints(self):
        from odap.biz.core.ontology.assistant.rules.constraint_suggester import (
            ConstraintSuggester,
        )
        suggester = ConstraintSuggester()
        result = suggester.suggest("xyz_unknown", "STRING")
        assert result["constraints"] == {}


class TestResponseType:
    def test_response_contains_property_name(self):
        from odap.biz.core.ontology.assistant.rules.constraint_suggester import (
            ConstraintSuggester,
        )
        suggester = ConstraintSuggester()
        result = suggester.suggest("email", "STRING")
        assert result["property_name"] == "email"

    def test_response_contains_data_type(self):
        from odap.biz.core.ontology.assistant.rules.constraint_suggester import (
            ConstraintSuggester,
        )
        suggester = ConstraintSuggester()
        result = suggester.suggest("age", "INTEGER")
        assert result["data_type"] == "INTEGER"

    def test_response_contains_source(self):
        from odap.biz.core.ontology.assistant.rules.constraint_suggester import (
            ConstraintSuggester,
        )
        suggester = ConstraintSuggester()
        result = suggester.suggest("email", "STRING")
        assert result["source"] == "rule_engine"
