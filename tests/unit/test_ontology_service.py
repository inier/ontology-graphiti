"""Comprehensive tests for OntologyService (ontology_api/services/ontology_service.py).

AGENTS.md rules:
- Rule 9: New modules must have corresponding test files.
- Rule C: SQLite storage tests use tmp_path real DB, NOT MagicMock.
- Service layer tests verify: success returns flat dict, error returns
  {"status": "error", "message": "..."}, type conversion (Enum->.value,
  datetime->.isoformat).

Coverage:
1. Ontology CRUD (create / get / list / update / delete + cascade)
2. Schema Version Management (commit / list / diff / rollback)
3. Type Definition CRUD (object / link / action / process / rule / function / indicator)
4. Graph Data (get_ontology_graph)
5. Database Connection (save / list / delete)
6. Extraction Session (create / get / update)
"""

import json
import pytest


# ---------------------------------------------------------------------------
# Fixture
# ---------------------------------------------------------------------------


@pytest.fixture
def service(tmp_path):
    """Create an OntologyService backed by a real temporary SQLite DB."""
    from odap.biz.core.ontology.ontology_api.services.ontology_service import (
        OntologyService,
    )

    db_path = str(tmp_path / "test_ontology_service.db")
    return OntologyService(db_path=db_path)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _create_ontology(service, name="Test Ontology", workspace_id="ws-1", **kwargs):
    """Shorthand to create an ontology and return the result dict."""
    return service.create_ontology(
        name=name, workspace_id=workspace_id, **kwargs
    )


def _is_error(result):
    """Check whether a service result dict represents an error."""
    return result.get("status") == "error"


# ===========================================================================
# 1. Ontology CRUD
# ===========================================================================


class TestOntologyCRUD:
    """Tests for create_ontology / get_ontology / list_ontologies /
    update_ontology / delete_ontology."""

    # -- create_ontology ---------------------------------------------------

    def test_create_ontology_success(self, service):
        result = service.create_ontology(name="My Ontology", workspace_id="ws-1")
        assert not _is_error(result)
        assert "ontology_id" in result
        assert result["name"] == "My Ontology"
        assert result["current_version"] == "v0.1.0"
        assert result["status"] == "draft"
        assert "created_at" in result
        assert "updated_at" in result

    def test_create_ontology_with_description(self, service):
        result = service.create_ontology(
            name="Ont", description="A description", workspace_id="ws-1"
        )
        assert not _is_error(result)
        assert result["description"] == "A description"

    def test_create_ontology_with_scenario_id(self, service):
        result = service.create_ontology(
            name="Ont", workspace_id="ws-1", scenario_id="sc-1"
        )
        assert not _is_error(result)
        assert result["scenario_id"] == "sc-1"

    def test_create_ontology_empty_name_returns_error(self, service):
        result = service.create_ontology(name="", workspace_id="ws-1")
        assert _is_error(result)
        assert "name" in result["message"].lower()

    def test_create_ontology_whitespace_name_returns_error(self, service):
        result = service.create_ontology(name="   ", workspace_id="ws-1")
        assert _is_error(result)

    def test_create_ontology_generates_unique_ids(self, service):
        r1 = service.create_ontology(name="A", workspace_id="ws-1")
        r2 = service.create_ontology(name="B", workspace_id="ws-1")
        assert r1["ontology_id"] != r2["ontology_id"]

    def test_create_ontology_initial_schema_version(self, service):
        """Creating an ontology should also create an initial v0.1.0 schema version."""
        result = service.create_ontology(name="Ont", workspace_id="ws-1")
        versions = service.list_schema_versions(result["ontology_id"])
        assert versions["count"] >= 1
        v = versions["versions"][0]
        assert v["version_number"] == "0.1.0"
        assert v["is_stable"] is False

    # -- get_ontology ------------------------------------------------------

    def test_get_ontology_success(self, service):
        created = _create_ontology(service)
        result = service.get_ontology(created["ontology_id"])
        assert not _is_error(result)
        assert result["ontology_id"] == created["ontology_id"]
        assert result["name"] == "Test Ontology"

    def test_get_ontology_nonexistent_returns_error(self, service):
        result = service.get_ontology("nonexistent-id")
        assert _is_error(result)
        assert "not found" in result["message"].lower()

    # -- list_ontologies ---------------------------------------------------

    def test_list_ontologies_empty(self, service):
        result = service.list_ontologies()
        assert not _is_error(result)
        assert result["ontologies"] == []
        assert result["count"] == 0

    def test_list_ontologies_returns_created(self, service):
        _create_ontology(service, name="A")
        _create_ontology(service, name="B")
        result = service.list_ontologies()
        assert result["count"] == 2
        names = {o["name"] for o in result["ontologies"]}
        assert names == {"A", "B"}

    def test_list_ontologies_filter_by_workspace(self, service):
        _create_ontology(service, name="WS1", workspace_id="ws-1")
        _create_ontology(service, name="WS2", workspace_id="ws-2")
        result = service.list_ontologies(workspace_id="ws-1")
        assert result["count"] == 1
        assert result["ontologies"][0]["name"] == "WS1"

    # -- update_ontology ---------------------------------------------------

    def test_update_ontology_success(self, service):
        created = _create_ontology(service)
        result = service.update_ontology(
            created["ontology_id"], {"name": "Updated", "description": "New desc"}
        )
        assert not _is_error(result)
        assert result["name"] == "Updated"
        assert result["description"] == "New desc"

    def test_update_ontology_updates_timestamp(self, service):
        created = _create_ontology(service)
        original_updated_at = created["updated_at"]
        result = service.update_ontology(
            created["ontology_id"], {"name": "Changed"}
        )
        assert result["updated_at"] != original_updated_at

    def test_update_ontology_nonexistent_returns_error(self, service):
        result = service.update_ontology("nonexistent-id", {"name": "X"})
        assert _is_error(result)
        assert "not found" in result["message"].lower()

    def test_update_ontology_ignores_non_updatable_fields(self, service):
        created = _create_ontology(service)
        result = service.update_ontology(
            created["ontology_id"], {"ontology_id": "hacked", "name": "NewName"}
        )
        assert result["name"] == "NewName"
        # ontology_id should NOT change
        assert result["ontology_id"] == created["ontology_id"]

    def test_update_ontology_status(self, service):
        created = _create_ontology(service)
        result = service.update_ontology(
            created["ontology_id"], {"status": "active"}
        )
        assert result["status"] == "active"

    # -- delete_ontology ---------------------------------------------------

    def test_delete_ontology_success(self, service):
        created = _create_ontology(service)
        result = service.delete_ontology(created["ontology_id"])
        assert result.get("deleted") is True
        assert result["ontology_id"] == created["ontology_id"]

    def test_delete_ontology_nonexistent_returns_error(self, service):
        result = service.delete_ontology("nonexistent-id")
        assert _is_error(result)

    def test_delete_ontology_cascade_deletes_type_definitions(self, service):
        """Deleting an ontology should cascade-delete all associated type definitions."""
        created = _create_ontology(service)
        oid = created["ontology_id"]

        # Create various type definitions
        service.create_object_type(oid, {"name": "ObjA"})
        service.create_link_type(oid, {"name": "LinkA", "source_type": "s", "target_type": "t"})
        service.create_action_type(oid, {"name": "ActA", "target_object_type": "ObjA"})
        service.create_process_type(oid, {"name": "ProcA"})
        service.create_rule_type(oid, {"name": "RuleA"})
        service.create_function_type(oid, {"name": "FuncA"})
        service.create_indicator_type(oid, {"name": "IndA"})

        result = service.delete_ontology(oid)
        assert result.get("deleted") is True

        # Verify all type lists are empty after cascade
        assert service.list_object_types(oid)["count"] == 0
        assert service.list_link_types(oid)["count"] == 0
        assert service.list_action_types(oid)["count"] == 0
        assert service.list_process_types(oid)["count"] == 0
        assert service.list_rule_types(oid)["count"] == 0
        assert service.list_function_types(oid)["count"] == 0
        assert service.list_indicator_types(oid)["count"] == 0

    def test_delete_ontology_cascade_deletes_schema_versions(self, service):
        created = _create_ontology(service)
        oid = created["ontology_id"]
        service.delete_ontology(oid)
        assert service.list_schema_versions(oid)["count"] == 0

    def test_delete_ontology_cascade_deletes_extraction_sessions(self, service):
        created = _create_ontology(service)
        oid = created["ontology_id"]
        service.create_extraction_session(oid, "document", {"source": "test"})
        service.delete_ontology(oid)
        # After cascade, there should be no sessions for this ontology
        # (we verify via storage directly since list_extraction_sessions
        # is not exposed on the service)
        from odap.biz.core.ontology.ontology_api.storage import Storage
        storage = Storage(db_path=service.storage.db_path)
        assert storage.list_extraction_sessions(oid) == []

    def test_delete_ontology_removes_from_list(self, service):
        created = _create_ontology(service)
        service.delete_ontology(created["ontology_id"])
        result = service.list_ontologies()
        assert result["count"] == 0


# ===========================================================================
# 2. Schema Version Management
# ===========================================================================


class TestSchemaVersionManagement:
    """Tests for commit_schema_version / list_schema_versions /
    diff_schema_versions / rollback_schema_version."""

    def _create_with_types(self, service):
        """Create an ontology with some type definitions for version testing."""
        created = _create_ontology(service, name="VersionTest")
        oid = created["ontology_id"]
        service.create_object_type(oid, {"name": "Person"})
        service.create_link_type(
            oid, {"name": "knows", "source_type": "Person", "target_type": "Person"}
        )
        return oid

    # -- commit_schema_version ---------------------------------------------

    def test_commit_schema_version_success(self, service):
        oid = self._create_with_types(service)
        result = service.commit_schema_version(oid, changelog="First commit")
        assert not _is_error(result)
        assert result["is_stable"] is True
        assert result["changelog"] == "First commit"
        assert "schema_snapshot" in result
        assert result["schema_snapshot"] is not None

    def test_commit_schema_version_marks_working_as_stable(self, service):
        oid = self._create_with_types(service)
        service.commit_schema_version(oid)
        versions = service.list_schema_versions(oid)
        # At least one version should be stable now
        stable = [v for v in versions["versions"] if v["is_stable"]]
        assert len(stable) >= 1

    def test_commit_schema_version_creates_new_working_version(self, service):
        oid = self._create_with_types(service)
        service.commit_schema_version(oid)
        versions = service.list_schema_versions(oid)
        working = [v for v in versions["versions"] if not v["is_stable"]]
        assert len(working) >= 1
        # New working version should have incremented minor version
        assert working[0]["version_number"] == "0.2.0"

    def test_commit_schema_version_updates_ontology_current_version(self, service):
        oid = self._create_with_types(service)
        service.commit_schema_version(oid)
        ont = service.get_ontology(oid)
        assert ont["current_version"] == "v0.2.0"

    def test_commit_schema_version_nonexistent_ontology_returns_error(self, service):
        result = service.commit_schema_version("nonexistent-id")
        assert _is_error(result)

    def test_commit_schema_version_snapshot_contains_types(self, service):
        oid = self._create_with_types(service)
        result = service.commit_schema_version(oid)
        snapshot = result["schema_snapshot"]
        assert len(snapshot.get("object_types", [])) >= 1
        assert len(snapshot.get("link_types", [])) >= 1

    def test_commit_schema_version_multiple_commits(self, service):
        """Multiple commits should create incrementing version numbers."""
        oid = self._create_with_types(service)
        service.commit_schema_version(oid, changelog="v1")
        service.commit_schema_version(oid, changelog="v2")
        versions = service.list_schema_versions(oid)
        # Should have: initial (0.1.0), committed (0.1.0 stable), working (0.2.0),
        # committed (0.2.0 stable), working (0.3.0)
        ont = service.get_ontology(oid)
        assert ont["current_version"] == "v0.3.0"

    # -- list_schema_versions ----------------------------------------------

    def test_list_schema_versions_success(self, service):
        oid = self._create_with_types(service)
        result = service.list_schema_versions(oid)
        assert not _is_error(result)
        assert "versions" in result
        assert result["count"] >= 1

    def test_list_schema_versions_empty(self, service):
        """An ontology with no versions (shouldn't happen via service, but test the path)."""
        # Create directly via storage to get an ontology without versions
        from odap.biz.core.ontology.ontology_api.storage import Storage
        storage = Storage(db_path=service.storage.db_path)
        storage.save_ontology({"ontology_id": "bare-ont", "name": "Bare", "workspace_id": "ws-1"})
        result = service.list_schema_versions("bare-ont")
        assert result["count"] == 0

    # -- diff_schema_versions ----------------------------------------------

    def test_diff_schema_versions_identical(self, service):
        oid = self._create_with_types(service)
        r1 = service.commit_schema_version(oid, changelog="v1")
        r2 = service.commit_schema_version(oid, changelog="v2")
        result = service.diff_schema_versions(
            oid, r1["version_id"], r2["version_id"]
        )
        assert not _is_error(result)
        assert "diff" in result
        # Both snapshots should have the same types, so no added/deleted
        for category in result["diff"]:
            assert result["diff"][category]["added_count"] == 0
            assert result["diff"][category]["deleted_count"] == 0

    def test_diff_schema_versions_with_changes(self, service):
        oid = self._create_with_types(service)
        r1 = service.commit_schema_version(oid, changelog="v1")

        # Add a new type after first commit
        service.create_object_type(oid, {"name": "Company"})
        r2 = service.commit_schema_version(oid, changelog="v2")

        result = service.diff_schema_versions(
            oid, r1["version_id"], r2["version_id"]
        )
        assert not _is_error(result)
        # object_types should show 1 added (Company)
        assert result["diff"]["object_types"]["added_count"] == 1

    def test_diff_schema_versions_nonexistent_version_returns_error(self, service):
        oid = self._create_with_types(service)
        result = service.diff_schema_versions(oid, "nonexistent-a", "nonexistent-b")
        assert _is_error(result)

    def test_diff_schema_versions_includes_version_info(self, service):
        oid = self._create_with_types(service)
        r1 = service.commit_schema_version(oid)
        r2 = service.commit_schema_version(oid)
        result = service.diff_schema_versions(
            oid, r1["version_id"], r2["version_id"]
        )
        assert "version_a" in result
        assert "version_b" in result
        assert result["version_a"]["version_id"] == r1["version_id"]
        assert result["version_b"]["version_id"] == r2["version_id"]

    # -- rollback_schema_version -------------------------------------------

    def test_rollback_schema_version_success(self, service):
        oid = self._create_with_types(service)
        r1 = service.commit_schema_version(oid, changelog="v1")

        # Add more types and commit again
        service.create_object_type(oid, {"name": "Company"})
        r2 = service.commit_schema_version(oid, changelog="v2")
        assert service.list_object_types(oid)["count"] == 2

        # Rollback to v1 (which had only Person)
        result = service.rollback_schema_version(oid, r1["version_id"])
        assert not _is_error(result)
        assert result["rolled_back_to"] == r1["version_id"]
        assert result["restored_types"]["object_types"] == 1

    def test_rollback_schema_version_restores_types(self, service):
        oid = self._create_with_types(service)
        r1 = service.commit_schema_version(oid, changelog="v1")

        # Add more types, then rollback
        service.create_object_type(oid, {"name": "Company"})
        service.rollback_schema_version(oid, r1["version_id"])

        # After rollback, only Person should exist
        types = service.list_object_types(oid)
        assert types["count"] == 1
        assert types["object_types"][0]["name"] == "Person"

    def test_rollback_schema_version_updates_ontology_version(self, service):
        oid = self._create_with_types(service)
        r1 = service.commit_schema_version(oid)
        service.rollback_schema_version(oid, r1["version_id"])
        ont = service.get_ontology(oid)
        assert ont["current_version"] == f"v{r1['version_number']}"

    def test_rollback_schema_version_nonexistent_ontology_returns_error(self, service):
        result = service.rollback_schema_version("nonexistent-id", "some-version")
        assert _is_error(result)

    def test_rollback_schema_version_nonexistent_version_returns_error(self, service):
        oid = self._create_with_types(service)
        result = service.rollback_schema_version(oid, "nonexistent-version")
        assert _is_error(result)

    def test_rollback_schema_version_no_snapshot_returns_error(self, service):
        """Rolling back to a version that has no snapshot should return error."""
        oid = self._create_with_types(service)
        # The initial working version has no snapshot
        versions = service.list_schema_versions(oid)
        working = [v for v in versions["versions"] if not v["is_stable"]]
        if working:
            result = service.rollback_schema_version(oid, working[0]["version_id"])
            assert _is_error(result)
            assert "no schema snapshot" in result["message"].lower()


# ===========================================================================
# 3. Type Definition CRUD
# ===========================================================================


# --- Object Type -----------------------------------------------------------


class TestObjectTypeCRUD:
    """Tests for create_object_type / get_object_type / list_object_types /
    update_object_type / delete_object_type."""

    def test_create_object_type_success(self, service):
        oid = _create_ontology(service)["ontology_id"]
        result = service.create_object_type(oid, {"name": "Person"})
        assert not _is_error(result)
        assert "type_id" in result
        assert result["name"] == "Person"
        assert result["ontology_id"] == oid
        assert result["is_active"] is True
        assert result["classification_level"] == "U"

    def test_create_object_type_with_all_fields(self, service):
        oid = _create_ontology(service)["ontology_id"]
        result = service.create_object_type(oid, {
            "name": "Person",
            "display_name": "Person Display",
            "description": "A person entity",
            "properties": [{"name": "age", "type": "int"}],
            "links": [{"name": "friend"}],
            "actions": [{"name": "greet"}],
            "primary_key": ["id"],
            "classification_level": "S",
            "icon": "user",
            "color": "#FF0000",
            "is_active": False,
            "parent_type": "Entity",
        })
        assert not _is_error(result)
        assert result["display_name"] == "Person Display"
        assert result["description"] == "A person entity"
        assert result["classification_level"] == "S"
        assert result["is_active"] is False
        assert result["parent_type"] == "Entity"

    def test_create_object_type_missing_name_returns_error(self, service):
        oid = _create_ontology(service)["ontology_id"]
        result = service.create_object_type(oid, {"description": "no name"})
        assert _is_error(result)
        assert "name" in result["message"].lower()

    def test_list_object_types_empty(self, service):
        oid = _create_ontology(service)["ontology_id"]
        result = service.list_object_types(oid)
        assert result["object_types"] == []
        assert result["count"] == 0

    def test_list_object_types_returns_created(self, service):
        oid = _create_ontology(service)["ontology_id"]
        service.create_object_type(oid, {"name": "A"})
        service.create_object_type(oid, {"name": "B"})
        result = service.list_object_types(oid)
        assert result["count"] == 2

    def test_update_object_type_success(self, service):
        oid = _create_ontology(service)["ontology_id"]
        created = service.create_object_type(oid, {"name": "Person"})
        result = service.update_object_type(
            created["type_id"], {"name": "Employee", "description": "An employee"}
        )
        assert not _is_error(result)
        assert result["name"] == "Employee"
        assert result["description"] == "An employee"

    def test_update_object_type_nonexistent_returns_error(self, service):
        result = service.update_object_type("nonexistent-id", {"name": "X"})
        assert _is_error(result)

    def test_delete_object_type_success(self, service):
        oid = _create_ontology(service)["ontology_id"]
        created = service.create_object_type(oid, {"name": "Person"})
        result = service.delete_object_type(created["type_id"])
        assert result.get("deleted") is True

    def test_delete_object_type_nonexistent_returns_error(self, service):
        result = service.delete_object_type("nonexistent-id")
        assert _is_error(result)


# --- Link Type -------------------------------------------------------------


class TestLinkTypeCRUD:
    """Tests for create_link_type / list_link_types / update_link_type /
    delete_link_type."""

    def test_create_link_type_success(self, service):
        oid = _create_ontology(service)["ontology_id"]
        result = service.create_link_type(oid, {
            "name": "knows",
            "source_type": "Person",
            "target_type": "Person",
        })
        assert not _is_error(result)
        assert "link_id" in result
        assert result["name"] == "knows"
        assert result["source_type"] == "Person"
        assert result["target_type"] == "Person"
        assert result["cardinality"] == "ONE_TO_MANY"
        assert result["link_type"] == "ASSOCIATION"

    def test_create_link_type_missing_name_returns_error(self, service):
        oid = _create_ontology(service)["ontology_id"]
        result = service.create_link_type(oid, {
            "source_type": "A", "target_type": "B"
        })
        assert _is_error(result)

    def test_create_link_type_missing_source_type_returns_error(self, service):
        oid = _create_ontology(service)["ontology_id"]
        result = service.create_link_type(oid, {
            "name": "link", "target_type": "B"
        })
        assert _is_error(result)
        assert "source_type" in result["message"].lower()

    def test_create_link_type_missing_target_type_returns_error(self, service):
        oid = _create_ontology(service)["ontology_id"]
        result = service.create_link_type(oid, {
            "name": "link", "source_type": "A"
        })
        assert _is_error(result)
        assert "target_type" in result["message"].lower()

    def test_create_link_type_with_optional_fields(self, service):
        oid = _create_ontology(service)["ontology_id"]
        result = service.create_link_type(oid, {
            "name": "employs",
            "source_type": "Company",
            "target_type": "Person",
            "cardinality": "ONE_TO_ONE",
            "link_type": "COMPOSITION",
            "is_bidirectional": True,
            "reverse_name": "employed_by",
            "description": "Employment relation",
        })
        assert not _is_error(result)
        assert result["cardinality"] == "ONE_TO_ONE"
        assert result["link_type"] == "COMPOSITION"
        assert result["is_bidirectional"] is True
        assert result["reverse_name"] == "employed_by"

    def test_list_link_types_empty(self, service):
        oid = _create_ontology(service)["ontology_id"]
        result = service.list_link_types(oid)
        assert result["link_types"] == []
        assert result["count"] == 0

    def test_list_link_types_returns_created(self, service):
        oid = _create_ontology(service)["ontology_id"]
        service.create_link_type(oid, {
            "name": "knows", "source_type": "P", "target_type": "P"
        })
        result = service.list_link_types(oid)
        assert result["count"] == 1

    def test_update_link_type_success(self, service):
        oid = _create_ontology(service)["ontology_id"]
        created = service.create_link_type(oid, {
            "name": "knows", "source_type": "P", "target_type": "P"
        })
        result = service.update_link_type(
            created["link_id"], {"name": "friends_with", "description": "Updated"}
        )
        assert not _is_error(result)
        assert result["name"] == "friends_with"
        assert result["description"] == "Updated"

    def test_update_link_type_nonexistent_returns_error(self, service):
        result = service.update_link_type("nonexistent-id", {"name": "X"})
        assert _is_error(result)

    def test_delete_link_type_success(self, service):
        oid = _create_ontology(service)["ontology_id"]
        created = service.create_link_type(oid, {
            "name": "knows", "source_type": "P", "target_type": "P"
        })
        result = service.delete_link_type(created["link_id"])
        assert result.get("deleted") is True

    def test_delete_link_type_nonexistent_returns_error(self, service):
        result = service.delete_link_type("nonexistent-id")
        assert _is_error(result)


# --- Action Type -----------------------------------------------------------


class TestActionTypeCRUD:
    """Tests for create_action_type / list_action_types / update_action_type /
    delete_action_type."""

    def test_create_action_type_success(self, service):
        oid = _create_ontology(service)["ontology_id"]
        result = service.create_action_type(oid, {
            "name": "approve",
            "target_object_type": "Order",
        })
        assert not _is_error(result)
        assert "action_type_id" in result
        assert result["name"] == "approve"
        assert result["target_object_type"] == "Order"
        assert result["confirmation_required"] is True

    def test_create_action_type_missing_name_returns_error(self, service):
        oid = _create_ontology(service)["ontology_id"]
        result = service.create_action_type(oid, {
            "target_object_type": "Order"
        })
        assert _is_error(result)

    def test_create_action_type_missing_target_object_type_returns_error(self, service):
        oid = _create_ontology(service)["ontology_id"]
        result = service.create_action_type(oid, {"name": "approve"})
        assert _is_error(result)
        assert "target_object_type" in result["message"].lower()

    def test_create_action_type_with_optional_fields(self, service):
        oid = _create_ontology(service)["ontology_id"]
        result = service.create_action_type(oid, {
            "name": "reject",
            "target_object_type": "Order",
            "description": "Reject an order",
            "parameters": [{"name": "reason", "type": "string"}],
            "required_roles": ["admin"],
            "confirmation_required": False,
        })
        assert not _is_error(result)
        assert result["description"] == "Reject an order"
        assert result["confirmation_required"] is False

    def test_list_action_types_empty(self, service):
        oid = _create_ontology(service)["ontology_id"]
        result = service.list_action_types(oid)
        assert result["action_types"] == []
        assert result["count"] == 0

    def test_list_action_types_returns_created(self, service):
        oid = _create_ontology(service)["ontology_id"]
        service.create_action_type(oid, {
            "name": "approve", "target_object_type": "Order"
        })
        result = service.list_action_types(oid)
        assert result["count"] == 1

    def test_update_action_type_success(self, service):
        oid = _create_ontology(service)["ontology_id"]
        created = service.create_action_type(oid, {
            "name": "approve", "target_object_type": "Order"
        })
        result = service.update_action_type(
            created["action_type_id"], {"name": "reject", "description": "Updated"}
        )
        assert not _is_error(result)
        assert result["name"] == "reject"

    def test_update_action_type_nonexistent_returns_error(self, service):
        result = service.update_action_type("nonexistent-id", {"name": "X"})
        assert _is_error(result)

    def test_delete_action_type_success(self, service):
        oid = _create_ontology(service)["ontology_id"]
        created = service.create_action_type(oid, {
            "name": "approve", "target_object_type": "Order"
        })
        result = service.delete_action_type(created["action_type_id"])
        assert result.get("deleted") is True

    def test_delete_action_type_nonexistent_returns_error(self, service):
        result = service.delete_action_type("nonexistent-id")
        assert _is_error(result)


# --- Process Type ----------------------------------------------------------


class TestProcessTypeCRUD:
    """Tests for create_process_type / list_process_types /
    update_process_type / delete_process_type."""

    def test_create_process_type_success(self, service):
        oid = _create_ontology(service)["ontology_id"]
        result = service.create_process_type(oid, {"name": "OrderProcess"})
        assert not _is_error(result)
        assert "type_id" in result
        assert result["name"] == "OrderProcess"

    def test_create_process_type_missing_name_returns_error(self, service):
        oid = _create_ontology(service)["ontology_id"]
        result = service.create_process_type(oid, {"description": "no name"})
        assert _is_error(result)

    def test_create_process_type_with_optional_fields(self, service):
        oid = _create_ontology(service)["ontology_id"]
        result = service.create_process_type(oid, {
            "name": "OrderProcess",
            "display_name": "Order Process",
            "description": "Process for orders",
            "flow_node_schema": [{"node": "start"}],
            "related_object_types": ["Order"],
        })
        assert not _is_error(result)
        assert result["display_name"] == "Order Process"

    def test_list_process_types_returns_created(self, service):
        oid = _create_ontology(service)["ontology_id"]
        service.create_process_type(oid, {"name": "P1"})
        result = service.list_process_types(oid)
        assert result["count"] == 1
        assert result["process_types"][0]["name"] == "P1"

    def test_update_process_type_success(self, service):
        oid = _create_ontology(service)["ontology_id"]
        created = service.create_process_type(oid, {"name": "P1"})
        result = service.update_process_type(
            created["type_id"], {"name": "P2", "description": "Updated"}
        )
        assert not _is_error(result)
        assert result["name"] == "P2"

    def test_update_process_type_nonexistent_returns_error(self, service):
        result = service.update_process_type("nonexistent-id", {"name": "X"})
        assert _is_error(result)

    def test_delete_process_type_success(self, service):
        oid = _create_ontology(service)["ontology_id"]
        created = service.create_process_type(oid, {"name": "P1"})
        result = service.delete_process_type(created["type_id"])
        assert result.get("deleted") is True

    def test_delete_process_type_nonexistent_returns_error(self, service):
        result = service.delete_process_type("nonexistent-id")
        assert _is_error(result)


# --- Rule Type -------------------------------------------------------------


class TestRuleTypeCRUD:
    """Tests for create_rule_type / list_rule_types / update_rule_type /
    delete_rule_type."""

    def test_create_rule_type_success(self, service):
        oid = _create_ontology(service)["ontology_id"]
        result = service.create_rule_type(oid, {"name": "DiscountRule"})
        assert not _is_error(result)
        assert "type_id" in result
        assert result["name"] == "DiscountRule"

    def test_create_rule_type_missing_name_returns_error(self, service):
        oid = _create_ontology(service)["ontology_id"]
        result = service.create_rule_type(oid, {"description": "no name"})
        assert _is_error(result)

    def test_create_rule_type_with_optional_fields(self, service):
        oid = _create_ontology(service)["ontology_id"]
        result = service.create_rule_type(oid, {
            "name": "DiscountRule",
            "display_name": "Discount Rule",
            "description": "Applies discount",
            "condition_schema": {"field": "amount", "op": "gt", "value": 100},
            "consequence_schema": {"field": "discount", "value": 0.1},
            "priority_levels": ["low", "critical"],
            "related_object_types": ["Order"],
        })
        assert not _is_error(result)
        assert result["display_name"] == "Discount Rule"

    def test_list_rule_types_returns_created(self, service):
        oid = _create_ontology(service)["ontology_id"]
        service.create_rule_type(oid, {"name": "R1"})
        result = service.list_rule_types(oid)
        assert result["count"] == 1

    def test_update_rule_type_success(self, service):
        oid = _create_ontology(service)["ontology_id"]
        created = service.create_rule_type(oid, {"name": "R1"})
        result = service.update_rule_type(
            created["type_id"], {"name": "R2", "description": "Updated"}
        )
        assert not _is_error(result)
        assert result["name"] == "R2"

    def test_update_rule_type_nonexistent_returns_error(self, service):
        result = service.update_rule_type("nonexistent-id", {"name": "X"})
        assert _is_error(result)

    def test_delete_rule_type_success(self, service):
        oid = _create_ontology(service)["ontology_id"]
        created = service.create_rule_type(oid, {"name": "R1"})
        result = service.delete_rule_type(created["type_id"])
        assert result.get("deleted") is True

    def test_delete_rule_type_nonexistent_returns_error(self, service):
        result = service.delete_rule_type("nonexistent-id")
        assert _is_error(result)


# --- Function Type ---------------------------------------------------------


class TestFunctionTypeCRUD:
    """Tests for create_function_type / list_function_types /
    update_function_type / delete_function_type."""

    def test_create_function_type_success(self, service):
        oid = _create_ontology(service)["ontology_id"]
        result = service.create_function_type(oid, {"name": "CalculateTotal"})
        assert not _is_error(result)
        assert "type_id" in result
        assert result["name"] == "CalculateTotal"

    def test_create_function_type_missing_name_returns_error(self, service):
        oid = _create_ontology(service)["ontology_id"]
        result = service.create_function_type(oid, {"description": "no name"})
        assert _is_error(result)

    def test_create_function_type_with_optional_fields(self, service):
        oid = _create_ontology(service)["ontology_id"]
        result = service.create_function_type(oid, {
            "name": "CalculateTotal",
            "display_name": "Calculate Total",
            "description": "Sum calculation",
            "logic_types": ["compute", "validate"],
            "expression_schema": {"type": "arithmetic"},
            "related_object_types": ["Order"],
        })
        assert not _is_error(result)
        assert result["display_name"] == "Calculate Total"

    def test_list_function_types_returns_created(self, service):
        oid = _create_ontology(service)["ontology_id"]
        service.create_function_type(oid, {"name": "F1"})
        result = service.list_function_types(oid)
        assert result["count"] == 1

    def test_update_function_type_success(self, service):
        oid = _create_ontology(service)["ontology_id"]
        created = service.create_function_type(oid, {"name": "F1"})
        result = service.update_function_type(
            created["type_id"], {"name": "F2", "description": "Updated"}
        )
        assert not _is_error(result)
        assert result["name"] == "F2"

    def test_update_function_type_nonexistent_returns_error(self, service):
        result = service.update_function_type("nonexistent-id", {"name": "X"})
        assert _is_error(result)

    def test_delete_function_type_success(self, service):
        oid = _create_ontology(service)["ontology_id"]
        created = service.create_function_type(oid, {"name": "F1"})
        result = service.delete_function_type(created["type_id"])
        assert result.get("deleted") is True

    def test_delete_function_type_nonexistent_returns_error(self, service):
        result = service.delete_function_type("nonexistent-id")
        assert _is_error(result)


# --- Indicator Type --------------------------------------------------------


class TestIndicatorTypeCRUD:
    """Tests for create_indicator_type / list_indicator_types /
    update_indicator_type / delete_indicator_type."""

    def test_create_indicator_type_success(self, service):
        oid = _create_ontology(service)["ontology_id"]
        result = service.create_indicator_type(oid, {"name": "Revenue"})
        assert not _is_error(result)
        assert "type_id" in result
        assert result["name"] == "Revenue"

    def test_create_indicator_type_missing_name_returns_error(self, service):
        oid = _create_ontology(service)["ontology_id"]
        result = service.create_indicator_type(oid, {"description": "no name"})
        assert _is_error(result)

    def test_create_indicator_type_with_optional_fields(self, service):
        oid = _create_ontology(service)["ontology_id"]
        result = service.create_indicator_type(oid, {
            "name": "Revenue",
            "display_name": "Revenue KPI",
            "description": "Total revenue",
            "indicator_types": ["kpi"],
            "formula_schema": {"type": "sum", "field": "amount"},
            "allowed_units": ["USD", "EUR"],
            "related_object_types": ["Order"],
        })
        assert not _is_error(result)
        assert result["display_name"] == "Revenue KPI"

    def test_list_indicator_types_returns_created(self, service):
        oid = _create_ontology(service)["ontology_id"]
        service.create_indicator_type(oid, {"name": "I1"})
        result = service.list_indicator_types(oid)
        assert result["count"] == 1

    def test_update_indicator_type_success(self, service):
        oid = _create_ontology(service)["ontology_id"]
        created = service.create_indicator_type(oid, {"name": "I1"})
        result = service.update_indicator_type(
            created["type_id"], {"name": "I2", "description": "Updated"}
        )
        assert not _is_error(result)
        assert result["name"] == "I2"

    def test_update_indicator_type_nonexistent_returns_error(self, service):
        result = service.update_indicator_type("nonexistent-id", {"name": "X"})
        assert _is_error(result)

    def test_delete_indicator_type_success(self, service):
        oid = _create_ontology(service)["ontology_id"]
        created = service.create_indicator_type(oid, {"name": "I1"})
        result = service.delete_indicator_type(created["type_id"])
        assert result.get("deleted") is True

    def test_delete_indicator_type_nonexistent_returns_error(self, service):
        result = service.delete_indicator_type("nonexistent-id")
        assert _is_error(result)


# ===========================================================================
# 4. Graph Data
# ===========================================================================


class TestGraphData:
    """Tests for get_ontology_graph."""

    def test_get_ontology_graph_empty(self, service):
        oid = _create_ontology(service)["ontology_id"]
        result = service.get_ontology_graph(oid)
        assert not _is_error(result)
        assert result["nodes"] == []
        assert result["edges"] == []

    def test_get_ontology_graph_with_objects_and_links(self, service):
        oid = _create_ontology(service)["ontology_id"]
        obj = service.create_object_type(oid, {"name": "Person"})
        link = service.create_link_type(oid, {
            "name": "knows",
            "source_type": "Person",
            "target_type": "Person",
        })

        result = service.get_ontology_graph(oid)
        assert not _is_error(result)
        assert len(result["nodes"]) == 1
        assert result["nodes"][0]["id"] == obj["type_id"]
        assert result["nodes"][0]["name"] == "Person"
        assert result["nodes"][0]["type"] == "object_type"

        assert len(result["edges"]) == 1
        assert result["edges"][0]["id"] == link["link_id"]
        assert result["edges"][0]["source"] == "Person"
        assert result["edges"][0]["target"] == "Person"
        assert result["edges"][0]["name"] == "knows"

    def test_get_ontology_graph_node_properties(self, service):
        oid = _create_ontology(service)["ontology_id"]
        service.create_object_type(oid, {
            "name": "Person",
            "properties": [{"name": "age"}, {"name": "name"}],
            "links": [{"name": "friend"}],
            "classification_level": "S",
        })

        result = service.get_ontology_graph(oid)
        node = result["nodes"][0]
        assert node["properties"]["property_count"] == 2
        assert node["properties"]["link_count"] == 1
        assert node["properties"]["classification_level"] == "S"

    def test_get_ontology_graph_edge_cardinality(self, service):
        oid = _create_ontology(service)["ontology_id"]
        service.create_link_type(oid, {
            "name": "employs",
            "source_type": "Company",
            "target_type": "Person",
            "cardinality": "ONE_TO_ONE",
            "link_type": "COMPOSITION",
        })

        result = service.get_ontology_graph(oid)
        edge = result["edges"][0]
        assert edge["cardinality"] == "ONE_TO_ONE"
        assert edge["type"] == "composition"

    def test_get_ontology_graph_nonexistent_ontology_returns_empty(self, service):
        """get_ontology_graph for a nonexistent ontology should return empty
        nodes/edges rather than error (since storage.list_* returns [])."""
        result = service.get_ontology_graph("nonexistent-id")
        assert not _is_error(result)
        assert result["nodes"] == []
        assert result["edges"] == []


# ===========================================================================
# 5. Database Connection
# ===========================================================================


class TestDatabaseConnection:
    """Tests for save_database_connection / list_database_connections /
    delete_database_connection."""

    def test_save_database_connection_success(self, service):
        result = service.save_database_connection({
            "name": "Prod DB",
            "db_type": "postgresql",
            "database": "mydb",
            "workspace_id": "ws-1",
        })
        assert not _is_error(result)
        assert "connection_id" in result
        assert result["name"] == "Prod DB"
        assert result["db_type"] == "postgresql"
        assert result["database"] == "mydb"
        assert result["host"] == "localhost"

    def test_save_database_connection_missing_name_returns_error(self, service):
        result = service.save_database_connection({
            "db_type": "postgresql",
            "database": "mydb",
            "workspace_id": "ws-1",
        })
        assert _is_error(result)
        assert "name" in result["message"].lower()

    def test_save_database_connection_missing_db_type_returns_error(self, service):
        result = service.save_database_connection({
            "name": "DB",
            "database": "mydb",
            "workspace_id": "ws-1",
        })
        assert _is_error(result)
        assert "db_type" in result["message"].lower()

    def test_save_database_connection_missing_database_returns_error(self, service):
        result = service.save_database_connection({
            "name": "DB",
            "db_type": "postgresql",
            "workspace_id": "ws-1",
        })
        assert _is_error(result)
        assert "database" in result["message"].lower()

    def test_save_database_connection_missing_workspace_id_returns_error(self, service):
        result = service.save_database_connection({
            "name": "DB",
            "db_type": "postgresql",
            "database": "mydb",
        })
        assert _is_error(result)
        assert "workspace_id" in result["message"].lower()

    def test_save_database_connection_with_all_fields(self, service):
        result = service.save_database_connection({
            "name": "Prod DB",
            "db_type": "mysql",
            "host": "db.example.com",
            "port": 3306,
            "database": "mydb",
            "username": "admin",
            "workspace_id": "ws-1",
        })
        assert not _is_error(result)
        assert result["host"] == "db.example.com"
        assert result["port"] == 3306

    def test_list_database_connections_empty(self, service):
        result = service.list_database_connections("ws-1")
        assert not _is_error(result)
        assert result["connections"] == []
        assert result["count"] == 0

    def test_list_database_connections_returns_created(self, service):
        service.save_database_connection({
            "name": "DB1", "db_type": "pg", "database": "db1", "workspace_id": "ws-1"
        })
        service.save_database_connection({
            "name": "DB2", "db_type": "mysql", "database": "db2", "workspace_id": "ws-1"
        })
        result = service.list_database_connections("ws-1")
        assert result["count"] == 2

    def test_list_database_connections_filters_by_workspace(self, service):
        service.save_database_connection({
            "name": "DB1", "db_type": "pg", "database": "db1", "workspace_id": "ws-1"
        })
        service.save_database_connection({
            "name": "DB2", "db_type": "pg", "database": "db2", "workspace_id": "ws-2"
        })
        result = service.list_database_connections("ws-1")
        assert result["count"] == 1
        assert result["connections"][0]["name"] == "DB1"

    def test_delete_database_connection_success(self, service):
        created = service.save_database_connection({
            "name": "DB", "db_type": "pg", "database": "db", "workspace_id": "ws-1"
        })
        result = service.delete_database_connection(created["connection_id"])
        assert result.get("deleted") is True

    def test_delete_database_connection_nonexistent_returns_error(self, service):
        result = service.delete_database_connection("nonexistent-id")
        assert _is_error(result)


# ===========================================================================
# 6. Extraction Session
# ===========================================================================


class TestExtractionSession:
    """Tests for create_extraction_session / get_extraction_session /
    update_extraction_session."""

    def test_create_extraction_session_success(self, service):
        oid = _create_ontology(service)["ontology_id"]
        result = service.create_extraction_session(
            oid, "document", {"source": "upload", "file_name": "test.pdf"}
        )
        assert not _is_error(result)
        assert "session_id" in result
        assert result["ontology_id"] == oid
        assert result["extraction_type"] == "document"
        assert result["status"] == "pending"
        assert result["result_data"] is None
        assert result["conflicts"] == []

    def test_create_extraction_session_empty_type_returns_error(self, service):
        oid = _create_ontology(service)["ontology_id"]
        result = service.create_extraction_session(oid, "", {"source": "test"})
        assert _is_error(result)

    def test_get_extraction_session_success(self, service):
        oid = _create_ontology(service)["ontology_id"]
        created = service.create_extraction_session(
            oid, "document", {"source": "test"}
        )
        result = service.get_extraction_session(created["session_id"])
        assert not _is_error(result)
        assert result["session_id"] == created["session_id"]
        assert result["extraction_type"] == "document"

    def test_get_extraction_session_nonexistent_returns_error(self, service):
        result = service.get_extraction_session("nonexistent-id")
        assert _is_error(result)
        assert "not found" in result["message"].lower()

    def test_update_extraction_session_status(self, service):
        oid = _create_ontology(service)["ontology_id"]
        created = service.create_extraction_session(
            oid, "document", {"source": "test"}
        )
        result = service.update_extraction_session(
            created["session_id"], {"status": "completed"}
        )
        assert not _is_error(result)
        assert result["status"] == "completed"

    def test_update_extraction_session_result_data(self, service):
        oid = _create_ontology(service)["ontology_id"]
        created = service.create_extraction_session(
            oid, "document", {"source": "test"}
        )
        result_data = {"entities": 5, "relations": 3}
        result = service.update_extraction_session(
            created["session_id"], {"result_data": result_data}
        )
        assert not _is_error(result)
        assert result["result_data"] == result_data

    def test_update_extraction_session_conflicts(self, service):
        oid = _create_ontology(service)["ontology_id"]
        created = service.create_extraction_session(
            oid, "document", {"source": "test"}
        )
        conflicts = [{"field": "name", "existing": "A", "proposed": "B"}]
        result = service.update_extraction_session(
            created["session_id"], {"conflicts": conflicts}
        )
        assert not _is_error(result)
        assert result["conflicts"] == conflicts

    def test_update_extraction_session_nonexistent_returns_error(self, service):
        result = service.update_extraction_session(
            "nonexistent-id", {"status": "completed"}
        )
        assert _is_error(result)


# ===========================================================================
# 7. Internal utility methods
# ===========================================================================


class TestInternalUtilities:
    """Tests for _increment_minor_version and _build_schema_snapshot."""

    def test_increment_minor_version_basic(self):
        from odap.biz.core.ontology.ontology_api.services.ontology_service import (
            OntologyService,
        )
        assert OntologyService._increment_minor_version("0.1.0") == "0.2.0"
        # Minor increment resets patch to 0 per semver convention
        assert OntologyService._increment_minor_version("1.3.5") == "1.4.0"
        assert OntologyService._increment_minor_version("2.0.0") == "2.1.0"

    def test_increment_minor_version_invalid_format(self):
        from odap.biz.core.ontology.ontology_api.services.ontology_service import (
            OntologyService,
        )
        assert OntologyService._increment_minor_version("invalid") == "0.2.0"
        assert OntologyService._increment_minor_version("1.2") == "0.2.0"
        assert OntologyService._increment_minor_version("") == "0.2.0"

    def test_build_schema_snapshot(self, service):
        oid = _create_ontology(service)["ontology_id"]
        service.create_object_type(oid, {"name": "Person"})
        service.create_link_type(oid, {
            "name": "knows", "source_type": "Person", "target_type": "Person"
        })
        service.create_action_type(oid, {
            "name": "approve", "target_object_type": "Order"
        })
        service.create_process_type(oid, {"name": "P1"})
        service.create_rule_type(oid, {"name": "R1"})
        service.create_function_type(oid, {"name": "F1"})
        service.create_indicator_type(oid, {"name": "I1"})

        snapshot = service._build_schema_snapshot(oid)
        assert len(snapshot["object_types"]) == 1
        assert len(snapshot["link_types"]) == 1
        assert len(snapshot["action_types"]) == 1
        assert len(snapshot["process_types"]) == 1
        assert len(snapshot["rule_types"]) == 1
        assert len(snapshot["function_types"]) == 1
        assert len(snapshot["indicator_types"]) == 1


# ===========================================================================
# 8. Cross-cutting: Service layer contract
# ===========================================================================


class TestServiceLayerContract:
    """Verify AGENTS.md rules for the service layer:
    - Success returns flat dict (no 'status' key or status != 'error')
    - Error returns {"status": "error", "message": "..."}
    - No HTTPException is raised from the service layer
    """

    def test_success_result_has_no_error_status(self, service):
        result = service.create_ontology(name="Contract", workspace_id="ws-1")
        assert result.get("status") != "error"

    def test_error_result_has_status_and_message(self, service):
        result = service.create_ontology(name="", workspace_id="ws-1")
        assert "status" in result
        assert result["status"] == "error"
        assert "message" in result
        assert isinstance(result["message"], str)
        assert len(result["message"]) > 0

    def test_list_result_has_count_field(self, service):
        result = service.list_ontologies()
        assert "count" in result
        assert isinstance(result["count"], int)

    def test_delete_result_has_deleted_flag(self, service):
        created = _create_ontology(service)
        result = service.delete_ontology(created["ontology_id"])
        assert "deleted" in result
        assert result["deleted"] is True

    def test_create_result_has_generated_id(self, service):
        result = service.create_ontology(name="ID Test", workspace_id="ws-1")
        assert "ontology_id" in result
        assert len(result["ontology_id"]) > 0

    def test_datetime_fields_are_iso_strings(self, service):
        result = service.create_ontology(name="Time Test", workspace_id="ws-1")
        assert isinstance(result["created_at"], str)
        assert isinstance(result["updated_at"], str)
        # ISO format should contain 'T'
        assert "T" in result["created_at"]

    def test_no_http_exception_raised(self, service):
        """Service layer should never raise HTTPException; errors are
        returned as dicts."""
        from fastapi import HTTPException

        # Try various error paths
        error_cases = [
            lambda: service.get_ontology("nonexistent"),
            lambda: service.update_ontology("nonexistent", {"name": "X"}),
            lambda: service.delete_ontology("nonexistent"),
            lambda: service.create_object_type("nonexistent", {}),
        ]
        for case in error_cases:
            result = case()
            # Should return error dict, not raise
            assert isinstance(result, dict)
            assert _is_error(result)
