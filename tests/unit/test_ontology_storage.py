"""Comprehensive tests for SQLiteOntologyStorage class.

Covers all 11 tables with full CRUD, JSON serialization/deserialization,
boolean conversion, batch deletes, and _safe_json_loads tolerance.

AGENTS.md Rule 9: New modules must have tests.
AGENTS.md Rule C: SQLite storage tests use tmp_path real DB, no MagicMock.
"""

import json

import pytest

from odap.infra.security.encryption import ClassifiedFieldEncryptor


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture(autouse=True)
def _reset_encryptor_singleton():
    """Reset the ClassifiedFieldEncryptor singleton before each test."""
    ClassifiedFieldEncryptor._instance = None
    ClassifiedFieldEncryptor._key = None
    yield
    ClassifiedFieldEncryptor._instance = None
    ClassifiedFieldEncryptor._key = None


@pytest.fixture
def storage(tmp_path):
    """Create a SQLiteOntologyStorage with a temp DB."""
    from odap.biz.core.ontology.ontology_api.storage.sqlite_ontology_storage import (
        SQLiteOntologyStorage,
    )

    db_path = str(tmp_path / "test_ontology.db")
    return SQLiteOntologyStorage(db_path=db_path)


# ---------------------------------------------------------------------------
# Factory helpers
# ---------------------------------------------------------------------------


def _make_ontology(**overrides):
    base = {
        "name": "test-ontology",
        "workspace_id": "ws-001",
        "description": "A test ontology",
        "scenario_id": "sc-001",
        "status": "DRAFT",
    }
    base.update(overrides)
    return base


def _make_schema_version(**overrides):
    base = {
        "ontology_id": "ont-001",
        "version_number": "v1.0.0",
        "is_stable": False,
        "changelog": "Initial version",
        "schema_snapshot": {"nodes": [], "edges": []},
    }
    base.update(overrides)
    return base


def _make_object_type(**overrides):
    base = {
        "ontology_id": "ont-001",
        "version_id": "ver-001",
        "name": "Person",
        "display_name": "Person",
        "description": "A person entity",
        "properties": [{"name": "age", "type": "integer"}],
        "links": [{"name": "works_at", "target": "Organization"}],
        "actions": [{"name": "promote", "type": "update"}],
        "primary_key": ["id"],
        "classification_level": "U",
        "icon": "user",
        "color": "#333",
        "is_active": True,
        "parent_type": None,
    }
    base.update(overrides)
    return base


def _make_link_type(**overrides):
    base = {
        "ontology_id": "ont-001",
        "version_id": "ver-001",
        "name": "works_at",
        "display_name": "Works At",
        "source_type": "Person",
        "target_type": "Organization",
        "cardinality": "MANY_TO_ONE",
        "link_type": "ASSOCIATION",
        "is_bidirectional": False,
        "reverse_name": "employees",
        "description": "Employment relationship",
    }
    base.update(overrides)
    return base


def _make_action_type(**overrides):
    base = {
        "ontology_id": "ont-001",
        "version_id": "ver-001",
        "name": "promote",
        "display_name": "Promote",
        "description": "Promote an employee",
        "target_object_type": "Person",
        "parameters": [{"name": "new_level", "type": "string"}],
        "required_roles": ["admin", "hr"],
        "confirmation_required": True,
    }
    base.update(overrides)
    return base


def _make_process_type(**overrides):
    base = {
        "ontology_id": "ont-001",
        "version_id": "ver-001",
        "name": "onboarding",
        "display_name": "Onboarding",
        "description": "Employee onboarding process",
        "flow_node_schema": [{"id": "n1", "type": "start"}],
        "related_object_types": ["Person", "Department"],
    }
    base.update(overrides)
    return base


def _make_rule_type(**overrides):
    base = {
        "ontology_id": "ont-001",
        "version_id": "ver-001",
        "name": "max_salary",
        "display_name": "Max Salary Rule",
        "description": "Salary cap rule",
        "condition_schema": {"field": "salary", "op": ">", "value": 100000},
        "consequence_schema": {"action": "flag", "severity": "high"},
        "priority_levels": ["low", "medium", "high"],
        "related_object_types": ["Person"],
    }
    base.update(overrides)
    return base


def _make_function_type(**overrides):
    base = {
        "ontology_id": "ont-001",
        "version_id": "ver-001",
        "name": "calculate_bonus",
        "display_name": "Calculate Bonus",
        "description": "Bonus calculation function",
        "logic_types": ["filter", "compute"],
        "expression_schema": {"expression": "salary * rate", "params": ["salary", "rate"]},
        "related_object_types": ["Person"],
    }
    base.update(overrides)
    return base


def _make_indicator_type(**overrides):
    base = {
        "ontology_id": "ont-001",
        "version_id": "ver-001",
        "name": "revenue",
        "display_name": "Revenue",
        "description": "Revenue indicator",
        "indicator_types": ["kpi"],
        "formula_schema": {"expression": "sum(income)", "period": "monthly"},
        "allowed_units": ["USD", "EUR", "CNY"],
        "related_object_types": ["Organization"],
    }
    base.update(overrides)
    return base


def _make_database_connection(**overrides):
    base = {
        "name": "test-conn",
        "db_type": "postgresql",
        "host": "localhost",
        "port": 5432,
        "database": "testdb",
        "username": "admin",
        "password_encrypted": "s3cret!",
        "workspace_id": "ws-001",
    }
    base.update(overrides)
    return base


def _make_extraction_session(**overrides):
    base = {
        "ontology_id": "ont-001",
        "extraction_type": "document",
        "status": "pending",
        "input_data": {"source": "upload", "files": ["doc1.pdf"]},
        "result_data": None,
        "conflicts": [],
    }
    base.update(overrides)
    return base


# ===================================================================
# 1. Ontologies CRUD
# ===================================================================


class TestOntologiesCRUD:
    """save_ontology / get_ontology / list_ontologies / delete_ontology"""

    def test_save_and_retrieve(self, storage):
        data = _make_ontology()
        saved = storage.save_ontology(data)
        assert saved is not None
        assert saved["name"] == "test-ontology"
        assert saved["workspace_id"] == "ws-001"
        assert saved["ontology_id"]  # auto-generated

        fetched = storage.get_ontology(saved["ontology_id"])
        assert fetched is not None
        assert fetched["name"] == "test-ontology"
        assert fetched["description"] == "A test ontology"
        assert fetched["scenario_id"] == "sc-001"
        assert fetched["status"] == "DRAFT"

    def test_save_with_explicit_id(self, storage):
        data = _make_ontology(ontology_id="ont-explicit")
        saved = storage.save_ontology(data)
        assert saved["ontology_id"] == "ont-explicit"

    def test_get_nonexistent_returns_none(self, storage):
        assert storage.get_ontology("nonexistent-id") is None

    def test_delete_existing(self, storage):
        saved = storage.save_ontology(_make_ontology())
        assert storage.delete_ontology(saved["ontology_id"]) is True
        assert storage.get_ontology(saved["ontology_id"]) is None

    def test_delete_nonexistent_returns_false(self, storage):
        assert storage.delete_ontology("nonexistent-id") is False

    def test_list_all(self, storage):
        storage.save_ontology(_make_ontology(name="ont-a"))
        storage.save_ontology(_make_ontology(name="ont-b"))
        all_onts = storage.list_ontologies()
        assert len(all_onts) == 2

    def test_list_with_workspace_filter(self, storage):
        storage.save_ontology(_make_ontology(name="ont-a", workspace_id="ws-001"))
        storage.save_ontology(_make_ontology(name="ont-b", workspace_id="ws-002"))
        filtered = storage.list_ontologies(workspace_id="ws-001")
        assert len(filtered) == 1
        assert filtered[0]["name"] == "ont-a"

    def test_list_empty_workspace(self, storage):
        assert storage.list_ontologies(workspace_id="ws-empty") == []

    def test_update_via_save_insert_or_replace(self, storage):
        saved = storage.save_ontology(_make_ontology(name="original"))
        ont_id = saved["ontology_id"]
        storage.save_ontology(
            _make_ontology(ontology_id=ont_id, name="updated", status="ACTIVE")
        )
        fetched = storage.get_ontology(ont_id)
        assert fetched["name"] == "updated"
        assert fetched["status"] == "ACTIVE"

    def test_created_at_and_updated_at_auto_set(self, storage):
        saved = storage.save_ontology(_make_ontology())
        assert saved["created_at"] is not None
        assert saved["updated_at"] is not None
        assert len(saved["created_at"]) > 0


# ===================================================================
# 2. Schema Versions CRUD
# ===================================================================


class TestSchemaVersionsCRUD:
    """save_schema_version / get_schema_version / list_schema_versions / delete_schema_version"""

    def test_save_and_retrieve(self, storage):
        storage.save_ontology(_make_ontology(ontology_id="ont-001"))
        data = _make_schema_version()
        saved = storage.save_schema_version(data)
        assert saved is not None
        assert saved["ontology_id"] == "ont-001"
        assert saved["version_number"] == "v1.0.0"

        fetched = storage.get_schema_version(saved["version_id"])
        assert fetched is not None
        assert fetched["changelog"] == "Initial version"

    def test_is_stable_boolean_conversion(self, storage):
        storage.save_ontology(_make_ontology(ontology_id="ont-001"))

        # is_stable=False
        saved = storage.save_schema_version(_make_schema_version(is_stable=False))
        assert saved["is_stable"] is False

        # is_stable=True
        saved2 = storage.save_schema_version(
            _make_schema_version(is_stable=True, version_number="v2.0.0")
        )
        assert saved2["is_stable"] is True

    def test_schema_snapshot_json_serialization(self, storage):
        storage.save_ontology(_make_ontology(ontology_id="ont-001"))
        snapshot = {"nodes": [{"id": "n1"}], "edges": [{"source": "n1", "target": "n2"}]}
        saved = storage.save_schema_version(
            _make_schema_version(schema_snapshot=snapshot)
        )
        fetched = storage.get_schema_version(saved["version_id"])
        assert fetched["schema_snapshot"] == snapshot

    def test_schema_snapshot_none(self, storage):
        storage.save_ontology(_make_ontology(ontology_id="ont-001"))
        saved = storage.save_schema_version(_make_schema_version(schema_snapshot=None))
        fetched = storage.get_schema_version(saved["version_id"])
        assert fetched["schema_snapshot"] is None

    def test_get_nonexistent_returns_none(self, storage):
        assert storage.get_schema_version("nonexistent-id") is None

    def test_delete_existing(self, storage):
        storage.save_ontology(_make_ontology(ontology_id="ont-001"))
        saved = storage.save_schema_version(_make_schema_version())
        assert storage.delete_schema_version(saved["version_id"]) is True
        assert storage.get_schema_version(saved["version_id"]) is None

    def test_delete_nonexistent_returns_false(self, storage):
        assert storage.delete_schema_version("nonexistent-id") is False

    def test_list_schema_versions(self, storage):
        storage.save_ontology(_make_ontology(ontology_id="ont-001"))
        storage.save_schema_version(
            _make_schema_version(version_number="v1.0.0")
        )
        storage.save_schema_version(
            _make_schema_version(version_number="v2.0.0")
        )
        versions = storage.list_schema_versions("ont-001")
        assert len(versions) == 2

    def test_list_schema_versions_other_ontology_empty(self, storage):
        storage.save_ontology(_make_ontology(ontology_id="ont-001"))
        storage.save_schema_version(_make_schema_version())
        assert storage.list_schema_versions("ont-999") == []

    def test_parent_version_id(self, storage):
        storage.save_ontology(_make_ontology(ontology_id="ont-001"))
        v1 = storage.save_schema_version(
            _make_schema_version(version_number="v1.0.0")
        )
        v2 = storage.save_schema_version(
            _make_schema_version(
                version_number="v2.0.0",
                parent_version_id=v1["version_id"],
            )
        )
        assert v2["parent_version_id"] == v1["version_id"]


# ===================================================================
# 3. Object Type Definitions CRUD
# ===================================================================


class TestObjectTypeDefinitionsCRUD:
    """save_object_type / get_object_type / list_object_types / list_object_types_by_version / delete_object_type"""

    def test_save_and_retrieve(self, storage):
        data = _make_object_type()
        saved = storage.save_object_type(data)
        assert saved is not None
        assert saved["name"] == "Person"

        fetched = storage.get_object_type(saved["type_id"])
        assert fetched is not None
        assert fetched["ontology_id"] == "ont-001"
        assert fetched["version_id"] == "ver-001"

    def test_json_fields_deserialize(self, storage):
        data = _make_object_type()
        saved = storage.save_object_type(data)
        fetched = storage.get_object_type(saved["type_id"])

        assert fetched["properties"] == [{"name": "age", "type": "integer"}]
        assert fetched["links"] == [{"name": "works_at", "target": "Organization"}]
        assert fetched["actions"] == [{"name": "promote", "type": "update"}]
        assert fetched["primary_key"] == ["id"]

    def test_is_active_boolean_conversion(self, storage):
        # is_active=True
        saved_true = storage.save_object_type(_make_object_type(name="Active", is_active=True))
        assert saved_true["is_active"] is True

        # is_active=False
        saved_false = storage.save_object_type(_make_object_type(name="Inactive", is_active=False))
        assert saved_false["is_active"] is False

    def test_get_nonexistent_returns_none(self, storage):
        assert storage.get_object_type("nonexistent-id") is None

    def test_delete_existing(self, storage):
        saved = storage.save_object_type(_make_object_type())
        assert storage.delete_object_type(saved["type_id"]) is True
        assert storage.get_object_type(saved["type_id"]) is None

    def test_delete_nonexistent_returns_false(self, storage):
        assert storage.delete_object_type("nonexistent-id") is False

    def test_list_by_ontology_id(self, storage):
        storage.save_object_type(_make_object_type(name="ObjA", ontology_id="ont-001"))
        storage.save_object_type(_make_object_type(name="ObjB", ontology_id="ont-001"))
        storage.save_object_type(_make_object_type(name="ObjC", ontology_id="ont-002"))
        result = storage.list_object_types("ont-001")
        assert len(result) == 2

    def test_list_by_version_id(self, storage):
        storage.save_object_type(_make_object_type(name="ObjA", version_id="ver-001"))
        storage.save_object_type(_make_object_type(name="ObjB", version_id="ver-002"))
        result = storage.list_object_types_by_version("ver-001")
        assert len(result) == 1
        assert result[0]["name"] == "ObjA"

    def test_classification_level_default(self, storage):
        saved = storage.save_object_type(_make_object_type())
        assert saved["classification_level"] == "U"

    def test_empty_json_fields_default(self, storage):
        saved = storage.save_object_type(
            {"ontology_id": "ont-001", "name": "EmptyFields"}
        )
        fetched = storage.get_object_type(saved["type_id"])
        assert fetched["properties"] == []
        assert fetched["links"] == []
        assert fetched["actions"] == []
        assert fetched["primary_key"] == []


# ===================================================================
# 4. Link Type Definitions CRUD
# ===================================================================


class TestLinkTypeDefinitionsCRUD:
    """save_link_type / get_link_type / list_link_types / list_link_types_by_version / delete_link_type"""

    def test_save_and_retrieve(self, storage):
        data = _make_link_type()
        saved = storage.save_link_type(data)
        assert saved is not None
        assert saved["name"] == "works_at"

        fetched = storage.get_link_type(saved["link_id"])
        assert fetched is not None
        assert fetched["source_type"] == "Person"
        assert fetched["target_type"] == "Organization"

    def test_is_bidirectional_boolean_conversion(self, storage):
        # is_bidirectional=False
        saved_false = storage.save_link_type(_make_link_type(name="link-f", is_bidirectional=False))
        assert saved_false["is_bidirectional"] is False

        # is_bidirectional=True
        saved_true = storage.save_link_type(_make_link_type(name="link-t", is_bidirectional=True))
        assert saved_true["is_bidirectional"] is True

    def test_get_nonexistent_returns_none(self, storage):
        assert storage.get_link_type("nonexistent-id") is None

    def test_delete_existing(self, storage):
        saved = storage.save_link_type(_make_link_type())
        assert storage.delete_link_type(saved["link_id"]) is True
        assert storage.get_link_type(saved["link_id"]) is None

    def test_delete_nonexistent_returns_false(self, storage):
        assert storage.delete_link_type("nonexistent-id") is False

    def test_list_by_ontology_id(self, storage):
        storage.save_link_type(_make_link_type(name="LinkA", ontology_id="ont-001"))
        storage.save_link_type(_make_link_type(name="LinkB", ontology_id="ont-002"))
        result = storage.list_link_types("ont-001")
        assert len(result) == 1
        assert result[0]["name"] == "LinkA"

    def test_list_by_version_id(self, storage):
        storage.save_link_type(_make_link_type(name="LinkA", version_id="ver-001"))
        storage.save_link_type(_make_link_type(name="LinkB", version_id="ver-002"))
        result = storage.list_link_types_by_version("ver-001")
        assert len(result) == 1
        assert result[0]["name"] == "LinkA"

    def test_cardinality_and_link_type_defaults(self, storage):
        saved = storage.save_link_type(
            {"ontology_id": "ont-001", "name": "default-link", "source_type": "A", "target_type": "B"}
        )
        assert saved["cardinality"] == "ONE_TO_MANY"
        assert saved["link_type"] == "ASSOCIATION"

    def test_reverse_name(self, storage):
        saved = storage.save_link_type(_make_link_type(reverse_name="employees"))
        assert saved["reverse_name"] == "employees"


# ===================================================================
# 5. Action Type Definitions CRUD
# ===================================================================


class TestActionTypeDefinitionsCRUD:
    """save_action_type / get_action_type / list_action_types / list_action_types_by_version / delete_action_type"""

    def test_save_and_retrieve(self, storage):
        data = _make_action_type()
        saved = storage.save_action_type(data)
        assert saved is not None
        assert saved["name"] == "promote"

        fetched = storage.get_action_type(saved["action_type_id"])
        assert fetched is not None
        assert fetched["target_object_type"] == "Person"

    def test_parameters_json_deserialization(self, storage):
        saved = storage.save_action_type(_make_action_type())
        fetched = storage.get_action_type(saved["action_type_id"])
        assert fetched["parameters"] == [{"name": "new_level", "type": "string"}]

    def test_required_roles_json_deserialization(self, storage):
        saved = storage.save_action_type(_make_action_type())
        fetched = storage.get_action_type(saved["action_type_id"])
        assert fetched["required_roles"] == ["admin", "hr"]

    def test_confirmation_required_boolean_conversion(self, storage):
        # confirmation_required=True
        saved_true = storage.save_action_type(
            _make_action_type(name="act-true", confirmation_required=True)
        )
        assert saved_true["confirmation_required"] is True

        # confirmation_required=False
        saved_false = storage.save_action_type(
            _make_action_type(name="act-false", confirmation_required=False)
        )
        assert saved_false["confirmation_required"] is False

    def test_get_nonexistent_returns_none(self, storage):
        assert storage.get_action_type("nonexistent-id") is None

    def test_delete_existing(self, storage):
        saved = storage.save_action_type(_make_action_type())
        assert storage.delete_action_type(saved["action_type_id"]) is True
        assert storage.get_action_type(saved["action_type_id"]) is None

    def test_delete_nonexistent_returns_false(self, storage):
        assert storage.delete_action_type("nonexistent-id") is False

    def test_list_by_ontology_id(self, storage):
        storage.save_action_type(_make_action_type(name="ActA", ontology_id="ont-001"))
        storage.save_action_type(_make_action_type(name="ActB", ontology_id="ont-002"))
        result = storage.list_action_types("ont-001")
        assert len(result) == 1
        assert result[0]["name"] == "ActA"

    def test_list_by_version_id(self, storage):
        storage.save_action_type(_make_action_type(name="ActA", version_id="ver-001"))
        storage.save_action_type(_make_action_type(name="ActB", version_id="ver-002"))
        result = storage.list_action_types_by_version("ver-001")
        assert len(result) == 1
        assert result[0]["name"] == "ActA"


# ===================================================================
# 6. Process Type Definitions CRUD
# ===================================================================


class TestProcessTypeDefinitionsCRUD:
    """save_process_type / get_process_type / list_process_types / list_process_types_by_version / delete_process_type"""

    def test_save_and_retrieve(self, storage):
        data = _make_process_type()
        saved = storage.save_process_type(data)
        assert saved is not None
        assert saved["name"] == "onboarding"

        fetched = storage.get_process_type(saved["type_id"])
        assert fetched is not None
        assert fetched["description"] == "Employee onboarding process"

    def test_flow_node_schema_json_deserialization(self, storage):
        saved = storage.save_process_type(_make_process_type())
        fetched = storage.get_process_type(saved["type_id"])
        assert fetched["flow_node_schema"] == [{"id": "n1", "type": "start"}]

    def test_related_object_types_json_deserialization(self, storage):
        saved = storage.save_process_type(_make_process_type())
        fetched = storage.get_process_type(saved["type_id"])
        assert fetched["related_object_types"] == ["Person", "Department"]

    def test_get_nonexistent_returns_none(self, storage):
        assert storage.get_process_type("nonexistent-id") is None

    def test_delete_existing(self, storage):
        saved = storage.save_process_type(_make_process_type())
        assert storage.delete_process_type(saved["type_id"]) is True
        assert storage.get_process_type(saved["type_id"]) is None

    def test_delete_nonexistent_returns_false(self, storage):
        assert storage.delete_process_type("nonexistent-id") is False

    def test_list_by_ontology_id(self, storage):
        storage.save_process_type(_make_process_type(name="ProcA", ontology_id="ont-001"))
        storage.save_process_type(_make_process_type(name="ProcB", ontology_id="ont-002"))
        result = storage.list_process_types("ont-001")
        assert len(result) == 1

    def test_list_by_version_id(self, storage):
        storage.save_process_type(_make_process_type(name="ProcA", version_id="ver-001"))
        storage.save_process_type(_make_process_type(name="ProcB", version_id="ver-002"))
        result = storage.list_process_types_by_version("ver-001")
        assert len(result) == 1
        assert result[0]["name"] == "ProcA"


# ===================================================================
# 7. Rule Type Definitions CRUD
# ===================================================================


class TestRuleTypeDefinitionsCRUD:
    """save_rule_type / get_rule_type / list_rule_types / list_rule_types_by_version / delete_rule_type"""

    def test_save_and_retrieve(self, storage):
        data = _make_rule_type()
        saved = storage.save_rule_type(data)
        assert saved is not None
        assert saved["name"] == "max_salary"

        fetched = storage.get_rule_type(saved["type_id"])
        assert fetched is not None
        assert fetched["description"] == "Salary cap rule"

    def test_condition_schema_json_deserialization(self, storage):
        saved = storage.save_rule_type(_make_rule_type())
        fetched = storage.get_rule_type(saved["type_id"])
        assert fetched["condition_schema"] == {
            "field": "salary",
            "op": ">",
            "value": 100000,
        }

    def test_consequence_schema_json_deserialization(self, storage):
        saved = storage.save_rule_type(_make_rule_type())
        fetched = storage.get_rule_type(saved["type_id"])
        assert fetched["consequence_schema"] == {"action": "flag", "severity": "high"}

    def test_priority_levels_json_deserialization(self, storage):
        saved = storage.save_rule_type(_make_rule_type())
        fetched = storage.get_rule_type(saved["type_id"])
        assert fetched["priority_levels"] == ["low", "medium", "high"]

    def test_related_object_types_json_deserialization(self, storage):
        saved = storage.save_rule_type(_make_rule_type())
        fetched = storage.get_rule_type(saved["type_id"])
        assert fetched["related_object_types"] == ["Person"]

    def test_get_nonexistent_returns_none(self, storage):
        assert storage.get_rule_type("nonexistent-id") is None

    def test_delete_existing(self, storage):
        saved = storage.save_rule_type(_make_rule_type())
        assert storage.delete_rule_type(saved["type_id"]) is True
        assert storage.get_rule_type(saved["type_id"]) is None

    def test_delete_nonexistent_returns_false(self, storage):
        assert storage.delete_rule_type("nonexistent-id") is False

    def test_list_by_ontology_id(self, storage):
        storage.save_rule_type(_make_rule_type(name="RuleA", ontology_id="ont-001"))
        storage.save_rule_type(_make_rule_type(name="RuleB", ontology_id="ont-002"))
        result = storage.list_rule_types("ont-001")
        assert len(result) == 1

    def test_list_by_version_id(self, storage):
        storage.save_rule_type(_make_rule_type(name="RuleA", version_id="ver-001"))
        storage.save_rule_type(_make_rule_type(name="RuleB", version_id="ver-002"))
        result = storage.list_rule_types_by_version("ver-001")
        assert len(result) == 1
        assert result[0]["name"] == "RuleA"


# ===================================================================
# 8. Function Type Definitions CRUD
# ===================================================================


class TestFunctionTypeDefinitionsCRUD:
    """save_function_type / get_function_type / list_function_types / list_function_types_by_version / delete_function_type"""

    def test_save_and_retrieve(self, storage):
        data = _make_function_type()
        saved = storage.save_function_type(data)
        assert saved is not None
        assert saved["name"] == "calculate_bonus"

        fetched = storage.get_function_type(saved["type_id"])
        assert fetched is not None
        assert fetched["description"] == "Bonus calculation function"

    def test_logic_types_json_deserialization(self, storage):
        saved = storage.save_function_type(_make_function_type())
        fetched = storage.get_function_type(saved["type_id"])
        assert fetched["logic_types"] == ["filter", "compute"]

    def test_expression_schema_json_deserialization(self, storage):
        saved = storage.save_function_type(_make_function_type())
        fetched = storage.get_function_type(saved["type_id"])
        assert fetched["expression_schema"] == {
            "expression": "salary * rate",
            "params": ["salary", "rate"],
        }

    def test_related_object_types_json_deserialization(self, storage):
        saved = storage.save_function_type(_make_function_type())
        fetched = storage.get_function_type(saved["type_id"])
        assert fetched["related_object_types"] == ["Person"]

    def test_get_nonexistent_returns_none(self, storage):
        assert storage.get_function_type("nonexistent-id") is None

    def test_delete_existing(self, storage):
        saved = storage.save_function_type(_make_function_type())
        assert storage.delete_function_type(saved["type_id"]) is True
        assert storage.get_function_type(saved["type_id"]) is None

    def test_delete_nonexistent_returns_false(self, storage):
        assert storage.delete_function_type("nonexistent-id") is False

    def test_list_by_ontology_id(self, storage):
        storage.save_function_type(_make_function_type(name="FuncA", ontology_id="ont-001"))
        storage.save_function_type(_make_function_type(name="FuncB", ontology_id="ont-002"))
        result = storage.list_function_types("ont-001")
        assert len(result) == 1

    def test_list_by_version_id(self, storage):
        storage.save_function_type(_make_function_type(name="FuncA", version_id="ver-001"))
        storage.save_function_type(_make_function_type(name="FuncB", version_id="ver-002"))
        result = storage.list_function_types_by_version("ver-001")
        assert len(result) == 1
        assert result[0]["name"] == "FuncA"


# ===================================================================
# 9. Indicator Type Definitions CRUD
# ===================================================================


class TestIndicatorTypeDefinitionsCRUD:
    """save_indicator_type / get_indicator_type / list_indicator_types / list_indicator_types_by_version / delete_indicator_type"""

    def test_save_and_retrieve(self, storage):
        data = _make_indicator_type()
        saved = storage.save_indicator_type(data)
        assert saved is not None
        assert saved["name"] == "revenue"

        fetched = storage.get_indicator_type(saved["type_id"])
        assert fetched is not None
        assert fetched["description"] == "Revenue indicator"

    def test_indicator_types_json_deserialization(self, storage):
        saved = storage.save_indicator_type(_make_indicator_type())
        fetched = storage.get_indicator_type(saved["type_id"])
        assert fetched["indicator_types"] == ["kpi"]

    def test_formula_schema_json_deserialization(self, storage):
        saved = storage.save_indicator_type(_make_indicator_type())
        fetched = storage.get_indicator_type(saved["type_id"])
        assert fetched["formula_schema"] == {
            "expression": "sum(income)",
            "period": "monthly",
        }

    def test_allowed_units_json_deserialization(self, storage):
        saved = storage.save_indicator_type(_make_indicator_type())
        fetched = storage.get_indicator_type(saved["type_id"])
        assert fetched["allowed_units"] == ["USD", "EUR", "CNY"]

    def test_related_object_types_json_deserialization(self, storage):
        saved = storage.save_indicator_type(_make_indicator_type())
        fetched = storage.get_indicator_type(saved["type_id"])
        assert fetched["related_object_types"] == ["Organization"]

    def test_get_nonexistent_returns_none(self, storage):
        assert storage.get_indicator_type("nonexistent-id") is None

    def test_delete_existing(self, storage):
        saved = storage.save_indicator_type(_make_indicator_type())
        assert storage.delete_indicator_type(saved["type_id"]) is True
        assert storage.get_indicator_type(saved["type_id"]) is None

    def test_delete_nonexistent_returns_false(self, storage):
        assert storage.delete_indicator_type("nonexistent-id") is False

    def test_list_by_ontology_id(self, storage):
        storage.save_indicator_type(_make_indicator_type(name="IndA", ontology_id="ont-001"))
        storage.save_indicator_type(_make_indicator_type(name="IndB", ontology_id="ont-002"))
        result = storage.list_indicator_types("ont-001")
        assert len(result) == 1

    def test_list_by_version_id(self, storage):
        storage.save_indicator_type(_make_indicator_type(name="IndA", version_id="ver-001"))
        storage.save_indicator_type(_make_indicator_type(name="IndB", version_id="ver-002"))
        result = storage.list_indicator_types_by_version("ver-001")
        assert len(result) == 1
        assert result[0]["name"] == "IndA"


# ===================================================================
# 10. Database Connections CRUD
# ===================================================================


class TestDatabaseConnectionsCRUD:
    """save_database_connection / get_database_connection / list_database_connections / delete_database_connection"""

    def test_save_and_retrieve(self, storage):
        data = _make_database_connection()
        saved = storage.save_database_connection(data)
        assert saved is not None
        assert saved["name"] == "test-conn"
        assert saved["db_type"] == "postgresql"

        fetched = storage.get_database_connection(saved["connection_id"])
        assert fetched is not None
        assert fetched["host"] == "localhost"
        assert fetched["port"] == 5432
        assert fetched["database"] == "testdb"
        assert fetched["username"] == "admin"

    def test_password_encrypted_decrypted_roundtrip(self, storage):
        data = _make_database_connection(password_encrypted="my_secret")
        saved = storage.save_database_connection(data)
        fetched = storage.get_database_connection(saved["connection_id"])
        assert fetched["password_encrypted"] == "my_secret"

    def test_list_by_workspace_id(self, storage):
        storage.save_database_connection(
            _make_database_connection(name="c1", workspace_id="ws-001")
        )
        storage.save_database_connection(
            _make_database_connection(name="c2", workspace_id="ws-002")
        )
        result = storage.list_database_connections("ws-001")
        assert len(result) == 1
        assert result[0]["name"] == "c1"

    def test_list_empty_workspace(self, storage):
        assert storage.list_database_connections("ws-empty") == []

    def test_get_nonexistent_returns_none(self, storage):
        assert storage.get_database_connection("nonexistent-id") is None

    def test_delete_existing(self, storage):
        saved = storage.save_database_connection(_make_database_connection())
        assert storage.delete_database_connection(saved["connection_id"]) is True
        assert storage.get_database_connection(saved["connection_id"]) is None

    def test_delete_nonexistent_returns_false(self, storage):
        assert storage.delete_database_connection("nonexistent-id") is False

    def test_none_password_stored_as_none(self, storage):
        data = _make_database_connection()
        del data["password_encrypted"]
        saved = storage.save_database_connection(data)
        assert saved.get("password_encrypted") is None

    def test_empty_password_stored_as_none(self, storage):
        data = _make_database_connection(password_encrypted="")
        saved = storage.save_database_connection(data)
        assert saved.get("password_encrypted") is None


# ===================================================================
# 11. Extraction Sessions CRUD
# ===================================================================


class TestExtractionSessionsCRUD:
    """save_extraction_session / get_extraction_session / update_extraction_session / list_extraction_sessions / delete_extraction_session"""

    def test_save_and_retrieve(self, storage):
        data = _make_extraction_session()
        saved = storage.save_extraction_session(data)
        assert saved is not None
        assert saved["extraction_type"] == "document"
        assert saved["status"] == "pending"

        fetched = storage.get_extraction_session(saved["session_id"])
        assert fetched is not None
        assert fetched["ontology_id"] == "ont-001"

    def test_input_data_json_deserialization(self, storage):
        input_data = {"source": "upload", "files": ["doc1.pdf"]}
        saved = storage.save_extraction_session(_make_extraction_session(input_data=input_data))
        fetched = storage.get_extraction_session(saved["session_id"])
        assert fetched["input_data"] == input_data

    def test_result_data_json_deserialization(self, storage):
        result_data = {"entities": 5, "relations": 3}
        saved = storage.save_extraction_session(
            _make_extraction_session(result_data=result_data)
        )
        fetched = storage.get_extraction_session(saved["session_id"])
        assert fetched["result_data"] == result_data

    def test_conflicts_json_deserialization(self, storage):
        conflicts = [{"field": "name", "existing": "A", "proposed": "B"}]
        saved = storage.save_extraction_session(
            _make_extraction_session(conflicts=conflicts)
        )
        fetched = storage.get_extraction_session(saved["session_id"])
        assert fetched["conflicts"] == conflicts

    def test_input_data_none(self, storage):
        saved = storage.save_extraction_session(
            _make_extraction_session(input_data=None)
        )
        fetched = storage.get_extraction_session(saved["session_id"])
        assert fetched["input_data"] is None

    def test_result_data_none(self, storage):
        saved = storage.save_extraction_session(
            _make_extraction_session(result_data=None)
        )
        fetched = storage.get_extraction_session(saved["session_id"])
        assert fetched["result_data"] is None

    def test_get_nonexistent_returns_none(self, storage):
        assert storage.get_extraction_session("nonexistent-id") is None

    def test_delete_existing(self, storage):
        saved = storage.save_extraction_session(_make_extraction_session())
        assert storage.delete_extraction_session(saved["session_id"]) is True
        assert storage.get_extraction_session(saved["session_id"]) is None

    def test_delete_nonexistent_returns_false(self, storage):
        assert storage.delete_extraction_session("nonexistent-id") is False

    def test_list_by_ontology_id(self, storage):
        storage.save_extraction_session(
            _make_extraction_session(ontology_id="ont-001")
        )
        storage.save_extraction_session(
            _make_extraction_session(ontology_id="ont-002")
        )
        result = storage.list_extraction_sessions("ont-001")
        assert len(result) == 1

    def test_update_extraction_session_partial_update(self, storage):
        saved = storage.save_extraction_session(_make_extraction_session())
        session_id = saved["session_id"]

        # Update status only
        updated = storage.update_extraction_session(
            session_id, {"status": "completed"}
        )
        assert updated is True
        fetched = storage.get_extraction_session(session_id)
        assert fetched["status"] == "completed"
        # Other fields should remain unchanged
        assert fetched["extraction_type"] == "document"

    def test_update_extraction_session_json_fields(self, storage):
        saved = storage.save_extraction_session(_make_extraction_session())
        session_id = saved["session_id"]

        new_result = {"entities": 10, "relations": 5}
        new_conflicts = [{"field": "x", "existing": "1", "proposed": "2"}]
        storage.update_extraction_session(
            session_id,
            {"result_data": new_result, "conflicts": new_conflicts},
        )
        fetched = storage.get_extraction_session(session_id)
        assert fetched["result_data"] == new_result
        assert fetched["conflicts"] == new_conflicts

    def test_update_extraction_session_nonexistent_returns_false(self, storage):
        result = storage.update_extraction_session("nonexistent-id", {"status": "done"})
        assert result is False

    def test_update_extraction_session_no_fields_returns_true(self, storage):
        saved = storage.save_extraction_session(_make_extraction_session())
        # Empty update dict (no allowed fields) should return True (no-op)
        result = storage.update_extraction_session(saved["session_id"], {})
        assert result is True


# ===================================================================
# 12. Batch Delete Methods
# ===================================================================


class TestBatchDeleteObjectTypes:
    """delete_object_types_by_ontology"""

    def test_deletes_correct_count(self, storage):
        storage.save_object_type(_make_object_type(type_id="ot-1", name="A"))
        storage.save_object_type(_make_object_type(type_id="ot-2", name="B"))
        storage.save_object_type(
            _make_object_type(type_id="ot-3", name="C", ontology_id="ont-002")
        )
        deleted = storage.delete_object_types_by_ontology("ont-001")
        assert deleted == 2
        assert storage.list_object_types("ont-001") == []
        # Other ontology unaffected
        assert len(storage.list_object_types("ont-002")) == 1

    def test_returns_zero_on_empty_table(self, storage):
        assert storage.delete_object_types_by_ontology("nonexistent") == 0


class TestBatchDeleteLinkTypes:
    """delete_link_types_by_ontology"""

    def test_deletes_correct_count(self, storage):
        storage.save_link_type(_make_link_type(link_id="lt-1", name="A"))
        storage.save_link_type(_make_link_type(link_id="lt-2", name="B"))
        deleted = storage.delete_link_types_by_ontology("ont-001")
        assert deleted == 2

    def test_returns_zero_on_empty_table(self, storage):
        assert storage.delete_link_types_by_ontology("nonexistent") == 0


class TestBatchDeleteActionTypes:
    """delete_action_types_by_ontology"""

    def test_deletes_correct_count(self, storage):
        storage.save_action_type(_make_action_type(action_type_id="at-1", name="A"))
        storage.save_action_type(_make_action_type(action_type_id="at-2", name="B"))
        deleted = storage.delete_action_types_by_ontology("ont-001")
        assert deleted == 2

    def test_returns_zero_on_empty_table(self, storage):
        assert storage.delete_action_types_by_ontology("nonexistent") == 0


class TestBatchDeleteProcessTypes:
    """delete_process_types_by_ontology"""

    def test_deletes_correct_count(self, storage):
        storage.save_process_type(_make_process_type(type_id="pt-1", name="A"))
        storage.save_process_type(_make_process_type(type_id="pt-2", name="B"))
        deleted = storage.delete_process_types_by_ontology("ont-001")
        assert deleted == 2

    def test_returns_zero_on_empty_table(self, storage):
        assert storage.delete_process_types_by_ontology("nonexistent") == 0


class TestBatchDeleteRuleTypes:
    """delete_rule_types_by_ontology"""

    def test_deletes_correct_count(self, storage):
        storage.save_rule_type(_make_rule_type(type_id="rt-1", name="A"))
        storage.save_rule_type(_make_rule_type(type_id="rt-2", name="B"))
        deleted = storage.delete_rule_types_by_ontology("ont-001")
        assert deleted == 2

    def test_returns_zero_on_empty_table(self, storage):
        assert storage.delete_rule_types_by_ontology("nonexistent") == 0


class TestBatchDeleteFunctionTypes:
    """delete_function_types_by_ontology"""

    def test_deletes_correct_count(self, storage):
        storage.save_function_type(_make_function_type(type_id="ft-1", name="A"))
        storage.save_function_type(_make_function_type(type_id="ft-2", name="B"))
        deleted = storage.delete_function_types_by_ontology("ont-001")
        assert deleted == 2

    def test_returns_zero_on_empty_table(self, storage):
        assert storage.delete_function_types_by_ontology("nonexistent") == 0


class TestBatchDeleteIndicatorTypes:
    """delete_indicator_types_by_ontology"""

    def test_deletes_correct_count(self, storage):
        storage.save_indicator_type(_make_indicator_type(type_id="it-1", name="A"))
        storage.save_indicator_type(_make_indicator_type(type_id="it-2", name="B"))
        deleted = storage.delete_indicator_types_by_ontology("ont-001")
        assert deleted == 2

    def test_returns_zero_on_empty_table(self, storage):
        assert storage.delete_indicator_types_by_ontology("nonexistent") == 0


class TestBatchDeleteSchemaVersions:
    """delete_schema_versions_by_ontology"""

    def test_deletes_correct_count(self, storage):
        storage.save_ontology(_make_ontology(ontology_id="ont-001"))
        storage.save_schema_version(
            _make_schema_version(version_id="sv-1", version_number="v1")
        )
        storage.save_schema_version(
            _make_schema_version(version_id="sv-2", version_number="v2")
        )
        deleted = storage.delete_schema_versions_by_ontology("ont-001")
        assert deleted == 2

    def test_returns_zero_on_empty_table(self, storage):
        assert storage.delete_schema_versions_by_ontology("nonexistent") == 0

    def test_does_not_affect_other_ontology(self, storage):
        storage.save_ontology(_make_ontology(ontology_id="ont-001"))
        storage.save_ontology(_make_ontology(ontology_id="ont-002"))
        storage.save_schema_version(
            _make_schema_version(version_id="sv-1", ontology_id="ont-001", version_number="v1")
        )
        storage.save_schema_version(
            _make_schema_version(version_id="sv-2", ontology_id="ont-002", version_number="v1")
        )
        storage.delete_schema_versions_by_ontology("ont-001")
        assert storage.get_schema_version("sv-2") is not None


class TestBatchDeleteExtractionSessions:
    """delete_extraction_sessions_by_ontology"""

    def test_deletes_correct_count(self, storage):
        storage.save_extraction_session(
            _make_extraction_session(session_id="es-1")
        )
        storage.save_extraction_session(
            _make_extraction_session(session_id="es-2")
        )
        deleted = storage.delete_extraction_sessions_by_ontology("ont-001")
        assert deleted == 2

    def test_returns_zero_on_empty_table(self, storage):
        assert storage.delete_extraction_sessions_by_ontology("nonexistent") == 0

    def test_does_not_affect_other_ontology(self, storage):
        storage.save_extraction_session(
            _make_extraction_session(session_id="es-1", ontology_id="ont-001")
        )
        storage.save_extraction_session(
            _make_extraction_session(session_id="es-2", ontology_id="ont-002")
        )
        storage.delete_extraction_sessions_by_ontology("ont-001")
        assert storage.get_extraction_session("es-2") is not None


# ===================================================================
# 13. Invalid JSON Tolerance (_safe_json_loads)
# ===================================================================


class TestSafeJsonLoads:
    """_safe_json_loads with invalid JSON returns default"""

    def test_valid_json_string(self):
        from odap.biz.core.ontology.ontology_api.storage.sqlite_ontology_storage import (
            _safe_json_loads,
        )

        assert _safe_json_loads('{"key": "value"}', {}) == {"key": "value"}

    def test_valid_json_list(self):
        from odap.biz.core.ontology.ontology_api.storage.sqlite_ontology_storage import (
            _safe_json_loads,
        )

        assert _safe_json_loads("[1, 2, 3]", []) == [1, 2, 3]

    def test_invalid_json_returns_default(self):
        from odap.biz.core.ontology.ontology_api.storage.sqlite_ontology_storage import (
            _safe_json_loads,
        )

        assert _safe_json_loads("not json at all", {"default": True}) == {"default": True}

    def test_invalid_json_broken_structure(self):
        from odap.biz.core.ontology.ontology_api.storage.sqlite_ontology_storage import (
            _safe_json_loads,
        )

        assert _safe_json_loads("{broken", []) == []

    def test_none_returns_default(self):
        from odap.biz.core.ontology.ontology_api.storage.sqlite_ontology_storage import (
            _safe_json_loads,
        )

        assert _safe_json_loads(None, {"default": True}) == {"default": True}

    def test_already_dict_passthrough(self):
        from odap.biz.core.ontology.ontology_api.storage.sqlite_ontology_storage import (
            _safe_json_loads,
        )

        data = {"already": "a dict"}
        assert _safe_json_loads(data, {}) is data

    def test_already_list_passthrough(self):
        from odap.biz.core.ontology.ontology_api.storage.sqlite_ontology_storage import (
            _safe_json_loads,
        )

        data = [1, 2, 3]
        assert _safe_json_loads(data, []) is data

    def test_type_error_returns_default(self):
        from odap.biz.core.ontology.ontology_api.storage.sqlite_ontology_storage import (
            _safe_json_loads,
        )

        # Passing an int which json.loads would reject
        assert _safe_json_loads(42, "default") == "default"


# ===================================================================
# 14. Invalid JSON tolerance in parsed rows
# ===================================================================


class TestInvalidJsonToleranceInRows:
    """Verify that corrupted JSON in DB columns degrades gracefully to defaults."""

    def test_object_type_corrupted_properties(self, storage):
        """If properties column has invalid JSON, it should default to []."""
        saved = storage.save_object_type(_make_object_type())
        type_id = saved["type_id"]

        # Directly corrupt the properties column
        import sqlite3

        conn = sqlite3.connect(storage.db_path)
        conn.execute(
            "UPDATE object_type_definitions SET properties = ? WHERE type_id = ?",
            ("{invalid json", type_id),
        )
        conn.commit()
        conn.close()

        fetched = storage.get_object_type(type_id)
        assert fetched["properties"] == []

    def test_object_type_corrupted_links(self, storage):
        saved = storage.save_object_type(_make_object_type())
        type_id = saved["type_id"]

        import sqlite3

        conn = sqlite3.connect(storage.db_path)
        conn.execute(
            "UPDATE object_type_definitions SET links = ? WHERE type_id = ?",
            ("not-json", type_id),
        )
        conn.commit()
        conn.close()

        fetched = storage.get_object_type(type_id)
        assert fetched["links"] == []

    def test_action_type_corrupted_parameters(self, storage):
        saved = storage.save_action_type(_make_action_type())
        action_type_id = saved["action_type_id"]

        import sqlite3

        conn = sqlite3.connect(storage.db_path)
        conn.execute(
            "UPDATE action_type_definitions SET parameters = ? WHERE action_type_id = ?",
            ("{bad", action_type_id),
        )
        conn.commit()
        conn.close()

        fetched = storage.get_action_type(action_type_id)
        assert fetched["parameters"] == []

    def test_rule_type_corrupted_condition_schema(self, storage):
        saved = storage.save_rule_type(_make_rule_type())
        type_id = saved["type_id"]

        import sqlite3

        conn = sqlite3.connect(storage.db_path)
        conn.execute(
            "UPDATE rule_type_definitions SET condition_schema = ? WHERE type_id = ?",
            ("{corrupted", type_id),
        )
        conn.commit()
        conn.close()

        fetched = storage.get_rule_type(type_id)
        assert fetched["condition_schema"] == {}

    def test_extraction_session_corrupted_input_data(self, storage):
        saved = storage.save_extraction_session(_make_extraction_session())
        session_id = saved["session_id"]

        import sqlite3

        conn = sqlite3.connect(storage.db_path)
        conn.execute(
            "UPDATE extraction_sessions SET input_data = ? WHERE session_id = ?",
            ("{bad-json", session_id),
        )
        conn.commit()
        conn.close()

        fetched = storage.get_extraction_session(session_id)
        assert fetched["input_data"] is None

    def test_extraction_session_corrupted_conflicts(self, storage):
        saved = storage.save_extraction_session(_make_extraction_session())
        session_id = saved["session_id"]

        import sqlite3

        conn = sqlite3.connect(storage.db_path)
        conn.execute(
            "UPDATE extraction_sessions SET conflicts = ? WHERE session_id = ?",
            ("{bad-json", session_id),
        )
        conn.commit()
        conn.close()

        fetched = storage.get_extraction_session(session_id)
        assert fetched["conflicts"] == []

    def test_process_type_corrupted_flow_node_schema(self, storage):
        saved = storage.save_process_type(_make_process_type())
        type_id = saved["type_id"]

        import sqlite3

        conn = sqlite3.connect(storage.db_path)
        conn.execute(
            "UPDATE process_type_definitions SET flow_node_schema = ? WHERE type_id = ?",
            ("{bad", type_id),
        )
        conn.commit()
        conn.close()

        fetched = storage.get_process_type(type_id)
        assert fetched["flow_node_schema"] == []

    def test_function_type_corrupted_logic_types(self, storage):
        saved = storage.save_function_type(_make_function_type())
        type_id = saved["type_id"]

        import sqlite3

        conn = sqlite3.connect(storage.db_path)
        conn.execute(
            "UPDATE function_type_definitions SET logic_types = ? WHERE type_id = ?",
            ("{bad", type_id),
        )
        conn.commit()
        conn.close()

        fetched = storage.get_function_type(type_id)
        assert fetched["logic_types"] == ["filter", "transform", "validate", "compute"]

    def test_indicator_type_corrupted_allowed_units(self, storage):
        saved = storage.save_indicator_type(_make_indicator_type())
        type_id = saved["type_id"]

        import sqlite3

        conn = sqlite3.connect(storage.db_path)
        conn.execute(
            "UPDATE indicator_type_definitions SET allowed_units = ? WHERE type_id = ?",
            ("{bad", type_id),
        )
        conn.commit()
        conn.close()

        fetched = storage.get_indicator_type(type_id)
        assert fetched["allowed_units"] == []

    def test_schema_version_corrupted_snapshot(self, storage):
        storage.save_ontology(_make_ontology(ontology_id="ont-001"))
        saved = storage.save_schema_version(_make_schema_version())
        version_id = saved["version_id"]

        import sqlite3

        conn = sqlite3.connect(storage.db_path)
        conn.execute(
            "UPDATE ontology_schema_versions SET schema_snapshot = ? WHERE version_id = ?",
            ("{bad-json", version_id),
        )
        conn.commit()
        conn.close()

        fetched = storage.get_schema_version(version_id)
        assert fetched["schema_snapshot"] is None


# ===================================================================
# 15. Update via INSERT OR REPLACE (upsert) for type definitions
# ===================================================================


class TestUpsertBehavior:
    """Verify that saving with the same ID updates the record."""

    def test_ontology_upsert(self, storage):
        saved = storage.save_ontology(_make_ontology(name="original"))
        ont_id = saved["ontology_id"]
        storage.save_ontology(_make_ontology(ontology_id=ont_id, name="updated"))
        fetched = storage.get_ontology(ont_id)
        assert fetched["name"] == "updated"

    def test_object_type_upsert(self, storage):
        saved = storage.save_object_type(_make_object_type(name="Original"))
        type_id = saved["type_id"]
        storage.save_object_type(
            _make_object_type(type_id=type_id, name="Updated")
        )
        fetched = storage.get_object_type(type_id)
        assert fetched["name"] == "Updated"

    def test_link_type_upsert(self, storage):
        saved = storage.save_link_type(_make_link_type(name="original-link"))
        link_id = saved["link_id"]
        storage.save_link_type(
            _make_link_type(link_id=link_id, name="updated-link")
        )
        fetched = storage.get_link_type(link_id)
        assert fetched["name"] == "updated-link"

    def test_action_type_upsert(self, storage):
        saved = storage.save_action_type(_make_action_type(name="original-act"))
        action_type_id = saved["action_type_id"]
        storage.save_action_type(
            _make_action_type(action_type_id=action_type_id, name="updated-act")
        )
        fetched = storage.get_action_type(action_type_id)
        assert fetched["name"] == "updated-act"

    def test_process_type_upsert(self, storage):
        saved = storage.save_process_type(_make_process_type(name="original-proc"))
        type_id = saved["type_id"]
        storage.save_process_type(
            _make_process_type(type_id=type_id, name="updated-proc")
        )
        fetched = storage.get_process_type(type_id)
        assert fetched["name"] == "updated-proc"

    def test_rule_type_upsert(self, storage):
        saved = storage.save_rule_type(_make_rule_type(name="original-rule"))
        type_id = saved["type_id"]
        storage.save_rule_type(
            _make_rule_type(type_id=type_id, name="updated-rule")
        )
        fetched = storage.get_rule_type(type_id)
        assert fetched["name"] == "updated-rule"

    def test_function_type_upsert(self, storage):
        saved = storage.save_function_type(_make_function_type(name="original-func"))
        type_id = saved["type_id"]
        storage.save_function_type(
            _make_function_type(type_id=type_id, name="updated-func")
        )
        fetched = storage.get_function_type(type_id)
        assert fetched["name"] == "updated-func"

    def test_indicator_type_upsert(self, storage):
        saved = storage.save_indicator_type(_make_indicator_type(name="original-ind"))
        type_id = saved["type_id"]
        storage.save_indicator_type(
            _make_indicator_type(type_id=type_id, name="updated-ind")
        )
        fetched = storage.get_indicator_type(type_id)
        assert fetched["name"] == "updated-ind"

    def test_database_connection_upsert(self, storage):
        saved = storage.save_database_connection(_make_database_connection(name="original"))
        conn_id = saved["connection_id"]
        storage.save_database_connection(
            _make_database_connection(connection_id=conn_id, name="updated")
        )
        fetched = storage.get_database_connection(conn_id)
        assert fetched["name"] == "updated"

    def test_extraction_session_upsert(self, storage):
        saved = storage.save_extraction_session(_make_extraction_session())
        session_id = saved["session_id"]
        storage.save_extraction_session(
            _make_extraction_session(session_id=session_id, status="completed")
        )
        fetched = storage.get_extraction_session(session_id)
        assert fetched["status"] == "completed"
