"""ValidationEngine unit tests (TDD — written FIRST, before implementation).

Covers User Story 4 (T038-T043):
- _validate_schema: type mismatch, missing required, undefined field, counts
- _validate_completeness: fill_rate, empty_rate, orphan_count, orphan_entities
- _score_confidence: per-entity scoring formula, threshold, needs_review
- _validate_references: dangling relations, invalid action targets, invalid rule refs
- validate: orchestration, summary, overall_status, EC-018 error handling
- Edge cases: empty result, all violations, all passed, exception

Rules (AGENTS.md):
- Pure logic tests — no external dependencies (no HE, no LLM, no DB)
- pytest classes grouped by validation dimension
- Expected values computed independently from spec, not from implementation
"""

import pytest

from odap.biz.data.hyper_extract.services.validation_engine import ValidationEngine


# ---------------------------------------------------------------------------
# Shared test fixtures / factories
# ---------------------------------------------------------------------------

def _make_schema() -> dict:
    """Build a canonical ontology schema for schema-validation tests.

    Defines:
    - object_types: Customer (id, name, age), Order (id, amount)
    - action_types: CreateOrder (target_type=Order)
    - rule_types: DiscountRule
    - link_types: places (Customer -> Order)
    """
    return {
        "object_types": [
            {
                "name": "Customer",
                "properties": [
                    {"name": "id", "type": "string", "required": True},
                    {"name": "name", "type": "string", "required": True},
                    {"name": "age", "type": "integer", "required": False},
                ],
            },
            {
                "name": "Order",
                "properties": [
                    {"name": "id", "type": "string", "required": True},
                    {"name": "amount", "type": "float", "required": True},
                ],
            },
        ],
        "action_types": [
            {"name": "CreateOrder", "target_type": "Order"},
        ],
        "rule_types": [
            {"name": "DiscountRule"},
        ],
        "link_types": [
            {"name": "places", "source": "Customer", "target": "Order"},
        ],
    }


def _make_entity(name: str = "Customer", etype: str = "object", **overrides) -> dict:
    """Factory for a single entity dict with sensible defaults."""
    entity = {"name": name, "type": etype, "description": f"{name} description"}
    entity.update(overrides)
    return entity


# ---------------------------------------------------------------------------
# 1. _validate_schema
# ---------------------------------------------------------------------------

class TestValidationEngineSchema:
    """Tests for ValidationEngine._validate_schema()."""

    def test_type_mismatch_detected(self):
        """Entity property type differs from schema → type_mismatch violation."""
        engine = ValidationEngine()
        entities = [
            _make_entity(
                properties={"id": "string", "name": "string", "age": "string"}
            )
        ]
        result = engine._validate_schema(entities, [], _make_schema())
        violations = result["violations"]
        mismatch = [v for v in violations if v["issue"] == "type_mismatch"]
        assert len(mismatch) == 1
        assert mismatch[0]["entity"] == "Customer"
        assert mismatch[0]["field"] == "age"
        assert mismatch[0]["expected"] == "integer"
        assert mismatch[0]["actual"] == "string"

    def test_missing_required_detected(self):
        """Required schema field absent from entity → missing_required violation."""
        engine = ValidationEngine()
        entities = [
            _make_entity(properties={"id": "string"})  # name is required, missing
        ]
        result = engine._validate_schema(entities, [], _make_schema())
        violations = result["violations"]
        missing = [v for v in violations if v["issue"] == "missing_required"]
        assert len(missing) == 1
        assert missing[0]["entity"] == "Customer"
        assert missing[0]["field"] == "name"

    def test_undefined_field_detected(self):
        """Entity has a field not in schema → undefined_field violation."""
        engine = ValidationEngine()
        entities = [
            _make_entity(
                properties={"id": "string", "name": "string", "email": "string"}
            )
        ]
        result = engine._validate_schema(entities, [], _make_schema())
        violations = result["violations"]
        undefined = [v for v in violations if v["issue"] == "undefined_field"]
        assert len(undefined) == 1
        assert undefined[0]["entity"] == "Customer"
        assert undefined[0]["field"] == "email"

    def test_all_fields_pass(self):
        """All entity fields match schema → violated_count == 0, passed_count > 0."""
        engine = ValidationEngine()
        entities = [
            _make_entity(
                properties={"id": "string", "name": "string", "age": "integer"}
            )
        ]
        result = engine._validate_schema(entities, [], _make_schema())
        assert result["violated_count"] == 0
        assert result["passed_count"] > 0
        assert result["violations"] == []

    def test_returns_passed_and_violated_counts(self):
        """Result contains passed_count and violated_count consistent with violations list."""
        engine = ValidationEngine()
        entities = [
            _make_entity(
                properties={"id": "string", "name": "string", "age": "string"}
            )
        ]
        result = engine._validate_schema(entities, [], _make_schema())
        assert result["violated_count"] == len(result["violations"])
        assert isinstance(result["passed_count"], int)
        assert isinstance(result["violated_count"], int)

    def test_multiple_entities_validated(self):
        """Multiple entities each checked independently."""
        engine = ValidationEngine()
        entities = [
            _make_entity(name="Customer", properties={"id": "string", "name": "string"}),
            _make_entity(name="Order", properties={"id": "string", "amount": "float"}),
        ]
        result = engine._validate_schema(entities, [], _make_schema())
        assert result["violated_count"] == 0
        assert result["passed_count"] >= 2

    def test_entity_not_in_schema_skipped(self):
        """Entity whose name is not in object_types is skipped (no crash)."""
        engine = ValidationEngine()
        entities = [
            _make_entity(name="Ghost", properties={"id": "string"}),
        ]
        result = engine._validate_schema(entities, [], _make_schema())
        # No schema to validate against → no violations for this entity
        assert result["violated_count"] == 0


# ---------------------------------------------------------------------------
# 2. _validate_completeness
# ---------------------------------------------------------------------------

class TestValidationEngineCompleteness:
    """Tests for ValidationEngine._validate_completeness()."""

    def test_fill_rate_calculation(self):
        """fill_rate = filled fields / total fields across all entities."""
        engine = ValidationEngine()
        entities = [
            {"name": "A", "type": "object", "description": "desc", "properties": {"id": "string"}},
            {"name": "B", "type": "object", "description": "", "properties": {}},
        ]
        # Entity A: 4 fields, all filled → 4 filled
        # Entity B: 4 fields, 2 empty (description="", properties={}) → 2 filled
        # Total: 8 fields, 6 filled → fill_rate = 0.75
        result = engine._validate_completeness(entities, [])
        assert result["fill_rate"] == pytest.approx(0.75, abs=1e-6)

    def test_empty_rate_calculation(self):
        """empty_rate = empty fields / total fields."""
        engine = ValidationEngine()
        entities = [
            {"name": "A", "type": "object", "description": "desc", "properties": {"id": "string"}},
            {"name": "B", "type": "object", "description": "", "properties": {}},
        ]
        # Total: 8 fields, 2 empty → empty_rate = 0.25
        result = engine._validate_completeness(entities, [])
        assert result["empty_rate"] == pytest.approx(0.25, abs=1e-6)

    def test_orphan_count_and_entities(self):
        """Entities not in any relation are orphans."""
        engine = ValidationEngine()
        entities = [
            {"name": "A", "type": "object"},
            {"name": "B", "type": "object"},
            {"name": "C", "type": "object"},
        ]
        relations = [
            {"source": "A", "target": "B", "relation_type": "knows"},
        ]
        result = engine._validate_completeness(entities, relations)
        assert result["orphan_count"] == 1
        assert "C" in result["orphan_entities"]

    def test_no_relations_all_orphans(self):
        """When there are no relations, every entity is an orphan."""
        engine = ValidationEngine()
        entities = [
            {"name": "A", "type": "object"},
            {"name": "B", "type": "object"},
        ]
        result = engine._validate_completeness(entities, [])
        assert result["orphan_count"] == 2
        assert set(result["orphan_entities"]) == {"A", "B"}

    def test_empty_entities_returns_zeros(self):
        """No entities → fill_rate=0, empty_rate=0, orphan_count=0."""
        engine = ValidationEngine()
        result = engine._validate_completeness([], [])
        assert result["fill_rate"] == 0
        assert result["empty_rate"] == 0
        assert result["orphan_count"] == 0
        assert result["orphan_entities"] == []

    def test_no_orphans_when_all_connected(self):
        """Every entity appears in at least one relation → orphan_count=0."""
        engine = ValidationEngine()
        entities = [
            {"name": "A", "type": "object"},
            {"name": "B", "type": "object"},
        ]
        relations = [
            {"source": "A", "target": "B", "relation_type": "knows"},
        ]
        result = engine._validate_completeness(entities, relations)
        assert result["orphan_count"] == 0
        assert result["orphan_entities"] == []


# ---------------------------------------------------------------------------
# 3. _score_confidence
# ---------------------------------------------------------------------------

class TestValidationEngineConfidence:
    """Tests for ValidationEngine._score_confidence()."""

    def test_score_calculation_formula(self):
        """Score = 0.4*fill + 0.3*template + 0.3*llm per entity."""
        engine = ValidationEngine()
        entities = [
            {"name": "A", "type": "object", "description": "desc", "properties": {"id": "string"}},
        ]
        # fill = 4/4 = 1.0 (all 4 fields filled)
        # llm = 2/2 = 1.0 (name + description both non-empty)
        # template = 0.8
        # score = 0.4*1.0 + 0.3*0.8 + 0.3*1.0 = 0.94
        result = engine._score_confidence(entities, template_score=0.8)
        assert result["per_entity"][0]["entity"] == "A"
        assert result["per_entity"][0]["score"] == pytest.approx(0.94, abs=1e-6)
        assert result["per_entity"][0]["components"]["fill"] == pytest.approx(1.0, abs=1e-6)
        assert result["per_entity"][0]["components"]["template"] == pytest.approx(0.8, abs=1e-6)
        assert result["per_entity"][0]["components"]["llm"] == pytest.approx(1.0, abs=1e-6)

    def test_below_threshold_added_to_needs_review(self):
        """Entity scoring below 0.6 is listed in needs_review."""
        engine = ValidationEngine()
        entities = [
            {"name": "B", "type": "object", "description": "", "properties": {}},
        ]
        # fill = 2/4 = 0.5 (name, type filled; description, properties empty)
        # llm = 1/2 = 0.5 (name filled, description empty)
        # template = 0.0
        # score = 0.4*0.5 + 0.3*0.0 + 0.3*0.5 = 0.35
        result = engine._score_confidence(entities, template_score=0.0)
        assert result["per_entity"][0]["score"] == pytest.approx(0.35, abs=1e-6)
        assert "B" in result["needs_review"]
        assert result["threshold"] == 0.6

    def test_custom_threshold(self):
        """Engine constructed with threshold=0.9 gates entities at 0.9."""
        engine = ValidationEngine(confidence_threshold=0.9)
        entities = [
            {"name": "C", "type": "object", "description": "desc", "properties": {}},
        ]
        # fill = 3/4 = 0.75 (properties is empty)
        # llm = 2/2 = 1.0
        # template = 0.5
        # score = 0.4*0.75 + 0.3*0.5 + 0.3*1.0 = 0.75
        # 0.75 < 0.9 → needs_review
        result = engine._score_confidence(entities, template_score=0.5)
        assert result["threshold"] == 0.9
        assert result["per_entity"][0]["score"] == pytest.approx(0.75, abs=1e-6)
        assert "C" in result["needs_review"]

    def test_all_entities_above_threshold(self):
        """When all entities score above threshold, needs_review is empty."""
        engine = ValidationEngine()
        entities = [
            {"name": "A", "type": "object", "description": "desc", "properties": {"id": "string"}},
            {"name": "B", "type": "object", "description": "desc", "properties": {"id": "string"}},
        ]
        # Both: fill=1.0, llm=1.0, template=0.8 → score=0.94 > 0.6
        result = engine._score_confidence(entities, template_score=0.8)
        assert result["needs_review"] == []
        assert len(result["per_entity"]) == 2

    def test_no_entities_returns_empty_lists(self):
        """No entities → per_entity=[], needs_review=[]."""
        engine = ValidationEngine()
        result = engine._score_confidence([], template_score=0.5)
        assert result["per_entity"] == []
        assert result["needs_review"] == []
        assert result["threshold"] == 0.6


# ---------------------------------------------------------------------------
# 4. _validate_references
# ---------------------------------------------------------------------------

class TestValidationEngineReferences:
    """Tests for ValidationEngine._validate_references()."""

    def test_dangling_relation_detected(self):
        """Relation whose source or target is not in entities → dangling."""
        engine = ValidationEngine()
        entities = [
            {"name": "A", "type": "object"},
        ]
        relations = [
            {"source": "A", "target": "Ghost", "relation_type": "knows"},
        ]
        result = engine._validate_references(entities, relations, _make_schema())
        dangling = result["dangling_relations"]
        assert len(dangling) == 1
        assert dangling[0]["source"] == "A"
        assert dangling[0]["target"] == "Ghost"
        assert dangling[0]["type"] == "knows"

    def test_invalid_action_target_detected(self):
        """Action entity target_type not in schema object_types → invalid."""
        engine = ValidationEngine()
        entities = [
            {"name": "CreateOrder", "type": "action", "target_type": "GhostType"},
        ]
        result = engine._validate_references(entities, [], _make_schema())
        invalid = result["invalid_action_targets"]
        assert len(invalid) == 1
        assert invalid[0]["action"] == "CreateOrder"
        assert invalid[0]["target_type"] == "GhostType"

    def test_invalid_rule_reference_detected(self):
        """Rule entity references an object not in schema → invalid."""
        engine = ValidationEngine()
        entities = [
            {"name": "DiscountRule", "type": "rule",
             "referenced_objects": ["Order", "GhostObject"]},
        ]
        result = engine._validate_references(entities, [], _make_schema())
        invalid = result["invalid_rule_references"]
        assert len(invalid) == 1
        assert invalid[0]["rule"] == "DiscountRule"
        assert invalid[0]["referenced_object"] == "GhostObject"

    def test_all_references_valid(self):
        """All relations, actions, and rules reference defined targets."""
        engine = ValidationEngine()
        entities = [
            {"name": "Customer", "type": "object"},
            {"name": "Order", "type": "object"},
            {"name": "CreateOrder", "type": "action", "target_type": "Order"},
            {"name": "DiscountRule", "type": "rule",
             "referenced_objects": ["Order", "Customer"]},
        ]
        relations = [
            {"source": "Customer", "target": "Order", "relation_type": "places"},
        ]
        result = engine._validate_references(entities, relations, _make_schema())
        assert result["dangling_relations"] == []
        assert result["invalid_action_targets"] == []
        assert result["invalid_rule_references"] == []

    def test_no_relations_no_dangling(self):
        """Empty relations list → no dangling relations."""
        engine = ValidationEngine()
        entities = [{"name": "A", "type": "object"}]
        result = engine._validate_references(entities, [], _make_schema())
        assert result["dangling_relations"] == []


# ---------------------------------------------------------------------------
# 5. validate() orchestration
# ---------------------------------------------------------------------------

class TestValidationEngineValidate:
    """Tests for ValidationEngine.validate() — the main entry point."""

    def test_orchestrates_all_four_dimensions(self):
        """validate() returns all 5 top-level keys in the report."""
        engine = ValidationEngine()
        result = engine.validate(
            {"entities": [], "relations": []},
            _make_schema(),
            template_score=0.5,
        )
        assert "schema_conformance" in result
        assert "completeness" in result
        assert "confidence" in result
        assert "referential_consistency" in result
        assert "summary" in result

    def test_summary_counts_correct(self):
        """Summary has correct total_entities, total_relations, needs_review_count."""
        engine = ValidationEngine()
        extraction = {
            "entities": [
                {"name": "Customer", "type": "object", "description": "d",
                 "properties": {"id": "string", "name": "string"}},
                {"name": "Order", "type": "object", "description": "d",
                 "properties": {"id": "string", "amount": "float"}},
            ],
            "relations": [
                {"source": "Customer", "target": "Order", "relation_type": "places"},
            ],
        }
        result = engine.validate(extraction, _make_schema(), template_score=0.8)
        summary = result["summary"]
        assert summary["total_entities"] == 2
        assert summary["total_relations"] == 1
        assert summary["needs_review_count"] == 0

    def test_overall_status_passed(self):
        """No violations, no needs_review → overall_status='passed'."""
        engine = ValidationEngine()
        extraction = {
            "entities": [
                {"name": "Customer", "type": "object", "description": "d",
                 "properties": {"id": "string", "name": "string"}},
            ],
            "relations": [],
        }
        result = engine.validate(extraction, _make_schema(), template_score=0.8)
        assert result["summary"]["overall_status"] == "passed"

    def test_overall_status_needs_review(self):
        """Low confidence but no critical issues → overall_status='needs_review'."""
        engine = ValidationEngine()
        extraction = {
            "entities": [
                {"name": "B", "type": "object", "description": "", "properties": {}},
            ],
            "relations": [],
        }
        # fill=0.5, llm=0.5, template=0.0 → score=0.35 < 0.6
        # No schema violations (B not in schema), no dangling refs
        result = engine.validate(extraction, _make_schema(), template_score=0.0)
        assert result["summary"]["overall_status"] == "needs_review"
        assert result["summary"]["needs_review_count"] == 1

    def test_overall_status_failed_on_schema_violation(self):
        """Schema violations present → overall_status='failed'."""
        engine = ValidationEngine()
        extraction = {
            "entities": [
                {"name": "Customer", "type": "object", "description": "d",
                 "properties": {"id": "string", "age": "string"}},
                # age type_mismatch (string vs integer) + missing_required (name)
            ],
            "relations": [],
        }
        result = engine.validate(extraction, _make_schema(), template_score=0.8)
        assert result["summary"]["overall_status"] == "failed"

    def test_overall_status_failed_on_dangling_relation(self):
        """Dangling relation → overall_status='failed'."""
        engine = ValidationEngine()
        extraction = {
            "entities": [
                {"name": "A", "type": "object", "description": "d",
                 "properties": {"id": "string"}},
            ],
            "relations": [
                {"source": "A", "target": "Ghost", "relation_type": "knows"},
            ],
        }
        result = engine.validate(extraction, _make_schema(), template_score=0.8)
        assert result["summary"]["overall_status"] == "failed"


# ---------------------------------------------------------------------------
# 6. Edge cases
# ---------------------------------------------------------------------------

class TestValidationEngineEdgeCases:
    """Edge case tests for ValidationEngine."""

    def test_empty_result(self):
        """No entities and no relations → status 'passed', all counts zero."""
        engine = ValidationEngine()
        result = engine.validate(
            {"entities": [], "relations": []},
            _make_schema(),
            template_score=0.5,
        )
        assert result["summary"]["total_entities"] == 0
        assert result["summary"]["total_relations"] == 0
        assert result["summary"]["needs_review_count"] == 0
        assert result["summary"]["overall_status"] == "passed"
        assert result["schema_conformance"]["violated_count"] == 0
        assert result["completeness"]["orphan_count"] == 0
        assert result["confidence"]["needs_review"] == []

    def test_all_violations(self):
        """Multiple violation types across all dimensions."""
        engine = ValidationEngine()
        extraction = {
            "entities": [
                # Schema: type_mismatch (age=string vs integer) + missing_required (name)
                {"name": "Customer", "type": "object", "description": "d",
                 "properties": {"id": "string", "age": "string"}},
                # Reference: invalid action target
                {"name": "BadAction", "type": "action", "target_type": "GhostType"},
                # Reference: invalid rule reference
                {"name": "BadRule", "type": "rule",
                 "referenced_objects": ["GhostObj"]},
            ],
            "relations": [
                # Dangling: target not in entities
                {"source": "Customer", "target": "NonExistent", "relation_type": "x"},
            ],
        }
        result = engine.validate(extraction, _make_schema(), template_score=0.0)
        assert result["summary"]["overall_status"] == "failed"
        assert result["schema_conformance"]["violated_count"] >= 1
        assert len(result["referential_consistency"]["dangling_relations"]) >= 1
        assert len(result["referential_consistency"]["invalid_action_targets"]) >= 1
        assert len(result["referential_consistency"]["invalid_rule_references"]) >= 1

    def test_all_passed(self):
        """Clean extraction with no issues → 'passed'."""
        engine = ValidationEngine()
        extraction = {
            "entities": [
                {"name": "Customer", "type": "object", "description": "A customer",
                 "properties": {"id": "string", "name": "string", "age": "integer"}},
                {"name": "Order", "type": "object", "description": "An order",
                 "properties": {"id": "string", "amount": "float"}},
                {"name": "CreateOrder", "type": "action",
                 "target_type": "Order", "description": "Creates an order"},
                {"name": "DiscountRule", "type": "rule",
                 "referenced_objects": ["Order", "Customer"],
                 "description": "Discount rule"},
            ],
            "relations": [
                {"source": "Customer", "target": "Order", "relation_type": "places"},
            ],
        }
        result = engine.validate(extraction, _make_schema(), template_score=0.8)
        assert result["summary"]["overall_status"] == "passed"
        assert result["schema_conformance"]["violated_count"] == 0
        assert result["summary"]["needs_review_count"] == 0

    def test_exception_returns_status_error(self):
        """EC-018: On exception, validate() returns status='error', does not block."""
        engine = ValidationEngine()
        # Passing None triggers an exception inside validate()
        result = engine.validate(None, _make_schema(), template_score=0.5)
        assert result.get("status") == "error"
        assert "message" in result
        assert result["summary"]["overall_status"] == "error"

    def test_exception_on_non_dict_input(self):
        """EC-018: Passing a string (non-dict) also returns status='error'."""
        engine = ValidationEngine()
        result = engine.validate("not a dict", _make_schema(), template_score=0.5)
        assert result.get("status") == "error"
        assert result["summary"]["overall_status"] == "error"

    def test_missing_entities_key_defaults_to_empty(self):
        """Missing 'entities' key is handled gracefully (treated as empty)."""
        engine = ValidationEngine()
        result = engine.validate({"relations": []}, _make_schema(), template_score=0.5)
        # Should not crash, should return a normal report
        assert "status" not in result or result.get("status") != "error"
        assert result["summary"]["total_entities"] == 0
