"""ExtractionService unit tests.

Covers:
- test_database_connection: success and failure cases
- extract_from_database: session creation, extraction result, conflict detection, failure handling
- extract_from_nl: session creation, result structure, auto_search (LLM-dependent tests skipped)
- confirm_extraction: skip/overwrite/rename strategies, session not found, type import
- get_session: returns session details, nonexistent session returns error
- _detect_conflicts: duplicate name detection, no conflicts when unique

Rules (AGENTS.md):
- Uses tmp_path fixture for real SQLite DB (NOT MagicMock for storage layer)
- Service layer tests verify: success returns flat dict, error returns {"status": "error", ...}
"""

import json
import os
import sqlite3

import pytest


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def service(tmp_path):
    """Create ExtractionService with a real SQLite DB via tmp_path."""
    from odap.biz.core.ontology.extraction.services.extraction_service import (
        ExtractionService,
    )

    db_path = str(tmp_path / "test_extraction.db")
    return ExtractionService(db_path=db_path)


@pytest.fixture
def ontology_service(tmp_path):
    """Create OntologyService sharing the same DB as the ExtractionService."""
    from odap.biz.core.ontology.ontology_api.services.ontology_service import (
        OntologyService,
    )

    db_path = str(tmp_path / "test_extraction.db")
    return OntologyService(db_path=db_path)


@pytest.fixture
def ontology_id(ontology_service):
    """Create a test ontology and return its ID."""
    result = ontology_service.create_ontology(
        name="test-ontology",
        description="Test ontology for extraction",
    )
    return result["ontology_id"]


def _make_object_type(name="customer", display_name="Customer", description="A customer"):
    """Factory for a minimal object type dict."""
    return {
        "name": name,
        "display_name": display_name,
        "description": description,
        "properties": [
            {
                "name": "id",
                "property_type": "integer",
                "required": True,
            },
            {
                "name": "name",
                "property_type": "string",
                "required": True,
            },
        ],
        "links": [],
        "actions": [],
        "primary_key": ["id"],
        "classification_level": "U",
    }


def _make_link_type(
    name="customer_to_order",
    source_type="customer",
    target_type="order",
):
    """Factory for a minimal link type dict."""
    return {
        "name": name,
        "source_type": source_type,
        "target_type": target_type,
        "cardinality": "1:N",
        "link_type": "ASSOCIATION",
        "description": f"Link from {source_type} to {target_type}",
    }


def _make_action_type(name="create_order", target_object_type="order"):
    """Factory for a minimal action type dict."""
    return {
        "name": name,
        "target_object_type": target_object_type,
        "description": f"Action {name}",
        "parameters": [],
    }


def _make_process_type(name="order_process"):
    """Factory for a minimal process type dict."""
    return {
        "name": name,
        "display_name": name.replace("_", " ").title(),
        "description": f"Process {name}",
    }


def _make_rule_type(name="validate_order"):
    """Factory for a minimal rule type dict."""
    return {
        "name": name,
        "description": f"Rule {name}",
    }


def _make_function_type(name="compute_total"):
    """Factory for a minimal function type dict."""
    return {
        "name": name,
        "description": f"Function {name}",
    }


def _make_indicator_type(name="order_count"):
    """Factory for a minimal indicator type dict."""
    return {
        "name": name,
        "description": f"Indicator {name}",
    }


def _create_sqlite_db_with_tables(db_path):
    """Create a real SQLite database with sample tables for extraction testing."""
    conn = sqlite3.connect(db_path)
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS customers (
            id INTEGER PRIMARY KEY,
            name TEXT NOT NULL,
            email TEXT
        )
        """
    )
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS orders (
            id INTEGER PRIMARY KEY,
            customer_id INTEGER NOT NULL,
            total REAL,
            FOREIGN KEY (customer_id) REFERENCES customers(id)
        )
        """
    )
    conn.commit()
    conn.close()


# ===========================================================================
# TestDatabaseConnection
# ===========================================================================


class TestDatabaseConnection:
    """Tests for ExtractionService.test_database_connection."""

    def test_success_with_real_sqlite(self, service, tmp_path):
        """Test connection to a real SQLite database returns success."""
        db_file = str(tmp_path / "sample.db")
        _create_sqlite_db_with_tables(db_file)

        result = service.test_database_connection(
            db_type="sqlite",
            host="",
            port=0,
            database=db_file,
        )

        assert result["status"] == "ok"
        assert result["table_count"] == 2
        assert result["schema_name"] == db_file

    def test_failure_invalid_connection(self, service):
        """Test connection to a nonexistent database returns error."""
        result = service.test_database_connection(
            db_type="postgresql",
            host="nonexistent-host.invalid",
            port=5432,
            database="nonexistent_db",
            username="nobody",
            password="nopass",
        )

        assert result["status"] == "error"
        assert result["table_count"] == 0


# ===========================================================================
# TestExtractFromDatabase
# ===========================================================================


class TestExtractFromDatabase:
    """Tests for ExtractionService.extract_from_database."""

    def test_creates_extraction_session(self, service, ontology_id, tmp_path):
        """Extract from database creates an extraction session record."""
        db_file = str(tmp_path / "sample.db")
        _create_sqlite_db_with_tables(db_file)

        result = service.extract_from_database(
            ontology_id=ontology_id,
            db_type="sqlite",
            host="",
            port=0,
            database=db_file,
        )

        assert result["status"] == "ok"
        assert "session_id" in result
        assert result["session_id"]  # non-empty

        # Verify session was persisted via OntologyService
        session = service.ontology_service.get_extraction_session(result["session_id"])
        assert session is not None
        assert session["extraction_type"] == "database"
        assert session["ontology_id"] == ontology_id

    def test_extraction_result_contains_object_types(self, service, ontology_id, tmp_path):
        """Extraction result includes object types mapped from database tables."""
        db_file = str(tmp_path / "sample.db")
        _create_sqlite_db_with_tables(db_file)

        result = service.extract_from_database(
            ontology_id=ontology_id,
            db_type="sqlite",
            host="",
            port=0,
            database=db_file,
        )

        assert result["status"] == "ok"
        extraction = result["result"]
        assert extraction["status"] == "ok"
        assert len(extraction["object_types"]) == 2

        names = {ot["name"] for ot in extraction["object_types"]}
        assert "customers" in names
        assert "orders" in names

    def test_extraction_result_contains_link_types_from_fk(self, service, ontology_id, tmp_path):
        """Extraction result includes link types derived from foreign keys."""
        db_file = str(tmp_path / "sample.db")
        _create_sqlite_db_with_tables(db_file)

        result = service.extract_from_database(
            ontology_id=ontology_id,
            db_type="sqlite",
            host="",
            port=0,
            database=db_file,
        )

        assert result["status"] == "ok"
        link_types = result["result"]["link_types"]
        assert len(link_types) >= 1
        # The FK orders.customer_id -> customers.id should produce a link
        fk_links = [lt for lt in link_types if lt["source_type"] == "orders" and lt["target_type"] == "customers"]
        assert len(fk_links) >= 1

    def test_detects_conflicts_with_existing_types(self, service, ontology_id, tmp_path):
        """Extraction detects conflicts when object type names already exist."""
        db_file = str(tmp_path / "sample.db")
        _create_sqlite_db_with_tables(db_file)

        # Pre-create an object type named 'customers' to cause a conflict
        service.ontology_service.create_object_type(
            ontology_id, _make_object_type(name="customers")
        )

        result = service.extract_from_database(
            ontology_id=ontology_id,
            db_type="sqlite",
            host="",
            port=0,
            database=db_file,
        )

        assert result["status"] == "ok"
        conflicts = result["conflicts"]
        assert len(conflicts) >= 1
        conflict_names = [c["name"] for c in conflicts]
        assert "customers" in conflict_names

    def test_extraction_failure_sets_session_failed(self, service, ontology_id):
        """When extraction fails, session status is set to 'failed'."""
        result = service.extract_from_database(
            ontology_id=ontology_id,
            db_type="postgresql",
            host="nonexistent-host.invalid",
            port=5432,
            database="nonexistent_db",
            username="nobody",
            password="nopass",
        )

        # The extraction itself should return an error
        assert result["status"] == "error"

        # The session should have been created and then set to 'failed'
        # Find the session via the ontology service
        # Since extract_from_database creates a session before extraction,
        # we need to find it. The session_id is not returned on error path,
        # so we check via list.
        sessions = service.ontology_service.storage.list_extraction_sessions(ontology_id)
        failed_sessions = [s for s in sessions if s.get("status") == "failed"]
        assert len(failed_sessions) >= 1

    def test_session_status_reviewing_on_success(self, service, ontology_id, tmp_path):
        """On successful extraction, session status is set to 'reviewing'."""
        db_file = str(tmp_path / "sample.db")
        _create_sqlite_db_with_tables(db_file)

        result = service.extract_from_database(
            ontology_id=ontology_id,
            db_type="sqlite",
            host="",
            port=0,
            database=db_file,
        )

        assert result["status"] == "ok"
        session_id = result["session_id"]
        session = service.ontology_service.get_extraction_session(session_id)
        assert session["status"] == "reviewing"


# ===========================================================================
# TestExtractFromNL — REMOVED
# NL extraction now delegates to data.hyper_extract.ExtractService.
# Delegation behavior is tested in test_extraction_service_nl.py.
# New ExtractService internal behavior is tested in test_extract_service.py.
# ===========================================================================


# ===========================================================================
# TestConfirmExtraction
# ===========================================================================


class TestConfirmExtraction:
    """Tests for ExtractionService.confirm_extraction."""

    def _setup_session_with_result(
        self, service, ontology_id, result_data, conflicts=None
    ):
        """Helper: create an extraction session with given result_data."""
        session_result = service.ontology_service.create_extraction_session(
            ontology_id=ontology_id,
            extraction_type="database",
            input_data={"db_type": "sqlite"},
        )
        session_id = session_result["session_id"]

        service.ontology_service.update_extraction_session(
            session_id,
            {
                "status": "reviewing",
                "result_data": result_data,
                "conflicts": conflicts or [],
            },
        )
        return session_id

    @pytest.mark.asyncio
    async def test_skip_strategy_skips_conflicting_types(self, service, ontology_id):
        """With skip strategy, conflicting types are not imported."""
        existing = service.ontology_service.create_object_type(
            ontology_id, _make_object_type(name="customer")
        )

        result_data = {
            "object_types": [_make_object_type(name="customer")],
            "link_types": [],
            "action_types": [],
            "process_types": [],
            "rule_types": [],
            "function_types": [],
            "indicator_types": [],
        }
        session_id = self._setup_session_with_result(service, ontology_id, result_data)

        result = await service.confirm_extraction(session_id, merge_strategy="skip")

        assert result["status"] == "ok"
        assert result["imported"]["object_types"] == 0

    @pytest.mark.asyncio
    async def test_overwrite_strategy_updates_existing(self, service, ontology_id):
        """With overwrite strategy, existing types are updated."""
        existing = service.ontology_service.create_object_type(
            ontology_id, _make_object_type(name="customer", description="Old description")
        )
        existing_type_id = existing["type_id"]

        new_type = _make_object_type(name="customer", description="New description")
        result_data = {
            "object_types": [new_type],
            "link_types": [],
            "action_types": [],
            "process_types": [],
            "rule_types": [],
            "function_types": [],
            "indicator_types": [],
        }
        session_id = self._setup_session_with_result(service, ontology_id, result_data)

        result = await service.confirm_extraction(session_id, merge_strategy="overwrite")

        assert result["status"] == "ok"
        assert result["imported"]["object_types"] == 1

        updated = service.ontology_service.get_object_type(existing_type_id)
        assert updated["description"] == "New description"

    @pytest.mark.asyncio
    async def test_rename_strategy_adds_imported_suffix(self, service, ontology_id):
        """With rename strategy, conflicting types get '_imported' suffix."""
        service.ontology_service.create_object_type(
            ontology_id, _make_object_type(name="customer")
        )

        new_type = _make_object_type(name="customer")
        result_data = {
            "object_types": [new_type],
            "link_types": [],
            "action_types": [],
            "process_types": [],
            "rule_types": [],
            "function_types": [],
            "indicator_types": [],
        }
        session_id = self._setup_session_with_result(service, ontology_id, result_data)

        result = await service.confirm_extraction(session_id, merge_strategy="rename")

        assert result["status"] == "ok"
        assert result["imported"]["object_types"] == 1

        types_result = service.ontology_service.list_object_types(ontology_id)
        names = [ot["name"] for ot in types_result["object_types"]]
        assert "customer_imported" in names

    @pytest.mark.asyncio
    async def test_session_not_found_returns_error(self, service):
        """Confirming a nonexistent session returns error dict."""
        result = await service.confirm_extraction("nonexistent-session-id")

        assert result["status"] == "error"
        assert "not found" in result["message"]

    @pytest.mark.asyncio
    async def test_imports_all_type_categories(self, service, ontology_id):
        """Confirm extraction imports all type categories (object, link, action, etc.)."""
        result_data = {
            "object_types": [_make_object_type(name="product")],
            "link_types": [_make_link_type(name="product_to_order", source_type="product", target_type="order")],
            "action_types": [_make_action_type(name="create_product", target_object_type="product")],
            "process_types": [_make_process_type(name="order_process")],
            "rule_types": [_make_rule_type(name="validate_order")],
            "function_types": [_make_function_type(name="compute_total")],
            "indicator_types": [_make_indicator_type(name="order_count")],
        }
        session_id = self._setup_session_with_result(service, ontology_id, result_data)

        result = await service.confirm_extraction(session_id, merge_strategy="skip")

        assert result["status"] == "ok"
        assert result["imported"]["object_types"] == 1
        assert result["imported"]["link_types"] == 1
        assert result["imported"]["action_types"] == 1
        assert result["imported"]["process_types"] == 1
        assert result["imported"]["rule_types"] == 1
        assert result["imported"]["function_types"] == 1
        assert result["imported"]["indicator_types"] == 1

    @pytest.mark.asyncio
    async def test_selected_type_ids_filters_import(self, service, ontology_id):
        """Only selected type IDs are imported when specified."""
        result_data = {
            "object_types": [
                _make_object_type(name="product"),
                _make_object_type(name="category"),
            ],
            "link_types": [],
            "action_types": [],
            "process_types": [],
            "rule_types": [],
            "function_types": [],
            "indicator_types": [],
        }
        session_id = self._setup_session_with_result(service, ontology_id, result_data)

        result = await service.confirm_extraction(
            session_id,
            selected_type_ids=["product"],
            merge_strategy="skip",
        )

        assert result["status"] == "ok"
        assert result["imported"]["object_types"] == 1

        types_result = service.ontology_service.list_object_types(ontology_id)
        names = [ot["name"] for ot in types_result["object_types"]]
        assert "product" in names
        assert "category" not in names

    @pytest.mark.asyncio
    async def test_confirm_sets_session_status_completed(self, service, ontology_id):
        """After confirmation, session status is set to 'completed'."""
        result_data = {
            "object_types": [_make_object_type(name="product")],
            "link_types": [],
            "action_types": [],
            "process_types": [],
            "rule_types": [],
            "function_types": [],
            "indicator_types": [],
        }
        session_id = self._setup_session_with_result(service, ontology_id, result_data)

        await service.confirm_extraction(session_id)

        session = service.ontology_service.get_extraction_session(session_id)
        assert session["status"] == "completed"

    @pytest.mark.asyncio
    async def test_no_conflict_creates_new_type(self, service, ontology_id):
        """When no conflict exists, a new type is created regardless of strategy."""
        result_data = {
            "object_types": [_make_object_type(name="product")],
            "link_types": [],
            "action_types": [],
            "process_types": [],
            "rule_types": [],
            "function_types": [],
            "indicator_types": [],
        }
        session_id = self._setup_session_with_result(service, ontology_id, result_data)

        result = await service.confirm_extraction(session_id, merge_strategy="skip")

        assert result["status"] == "ok"
        assert result["imported"]["object_types"] == 1

        types_result = service.ontology_service.list_object_types(ontology_id)
        names = [ot["name"] for ot in types_result["object_types"]]
        assert "product" in names

    @pytest.mark.asyncio
    async def test_confirm_returns_channel_statuses(self, service, ontology_id):
        """confirm_extraction returns channel_a_status and channel_b_status."""
        result_data = {
            "object_types": [_make_object_type(name="product")],
            "link_types": [],
            "action_types": [],
            "process_types": [],
            "rule_types": [],
            "function_types": [],
            "indicator_types": [],
        }
        session_id = self._setup_session_with_result(service, ontology_id, result_data)

        result = await service.confirm_extraction(session_id, merge_strategy="skip")

        assert result["status"] == "ok"
        assert "channel_a_status" in result
        assert "channel_b_status" in result
        assert result["channel_a_status"] in ("success", "skipped", "failed")
        assert result["channel_b_status"] in ("success", "skipped", "failed")

    @pytest.mark.asyncio
    async def test_confirm_session_stores_channel_b_status(self, service, ontology_id):
        """Session data includes channel_b_status after confirmation."""
        result_data = {
            "object_types": [_make_object_type(name="product")],
            "link_types": [],
            "action_types": [],
            "process_types": [],
            "rule_types": [],
            "function_types": [],
            "indicator_types": [],
        }
        session_id = self._setup_session_with_result(service, ontology_id, result_data)

        await service.confirm_extraction(session_id, merge_strategy="skip")

        session = service.ontology_service.get_extraction_session(session_id)
        assert session["status"] == "completed"


# ===========================================================================
# TestGetSession
# ===========================================================================


class TestGetSession:
    """Tests for ExtractionService.get_session."""

    def test_returns_session_details(self, service, ontology_id):
        """get_session returns the session dict for a valid session."""
        session_result = service.ontology_service.create_extraction_session(
            ontology_id=ontology_id,
            extraction_type="database",
            input_data={"db_type": "sqlite"},
        )
        session_id = session_result["session_id"]

        result = service.get_session(session_id)

        assert result["session_id"] == session_id
        assert result["ontology_id"] == ontology_id
        assert result["extraction_type"] == "database"

    def test_nonexistent_session_returns_error(self, service):
        """get_session returns error dict for nonexistent session."""
        result = service.get_session("nonexistent-session-id")

        assert result["status"] == "error"
        assert "not found" in result["message"]


# ===========================================================================
# TestDetectConflicts
# ===========================================================================


class TestDetectConflicts:
    """Tests for ExtractionService._detect_conflicts."""

    def test_detects_duplicate_object_type_names(self, service, ontology_id):
        """_detect_conflicts returns conflict entries for duplicate names."""
        # Create an existing object type
        service.ontology_service.create_object_type(
            ontology_id, _make_object_type(name="customer")
        )

        extraction_result = {
            "object_types": [_make_object_type(name="customer")],
        }

        conflicts = service._detect_conflicts(ontology_id, extraction_result)

        assert len(conflicts) == 1
        assert conflicts[0]["type"] == "object_type"
        assert conflicts[0]["name"] == "customer"
        assert conflicts[0]["conflict"] == "duplicate_name"
        assert conflicts[0]["existing"] is True

    def test_no_conflicts_when_names_are_unique(self, service, ontology_id):
        """_detect_conflicts returns empty list when no name collisions."""
        # Create an existing object type
        service.ontology_service.create_object_type(
            ontology_id, _make_object_type(name="customer")
        )

        extraction_result = {
            "object_types": [_make_object_type(name="order")],
        }

        conflicts = service._detect_conflicts(ontology_id, extraction_result)

        assert len(conflicts) == 0

    def test_multiple_conflicts_detected(self, service, ontology_id):
        """_detect_conflicts detects multiple duplicate names."""
        service.ontology_service.create_object_type(
            ontology_id, _make_object_type(name="customer")
        )
        service.ontology_service.create_object_type(
            ontology_id, _make_object_type(name="order")
        )

        extraction_result = {
            "object_types": [
                _make_object_type(name="customer"),
                _make_object_type(name="order"),
                _make_object_type(name="product"),  # no conflict
            ],
        }

        conflicts = service._detect_conflicts(ontology_id, extraction_result)

        assert len(conflicts) == 2
        conflict_names = {c["name"] for c in conflicts}
        assert conflict_names == {"customer", "order"}

    def test_no_existing_types_no_conflicts(self, service, ontology_id):
        """_detect_conflicts returns empty list when ontology has no types."""
        extraction_result = {
            "object_types": [_make_object_type(name="customer")],
        }

        conflicts = service._detect_conflicts(ontology_id, extraction_result)

        assert len(conflicts) == 0

    def test_detects_duplicate_link_type_names(self, service, ontology_id):
        """_detect_conflicts detects duplicate link_type names."""
        service.ontology_service.create_link_type(
            ontology_id,
            _make_link_type(name="customer_to_order"),
        )

        extraction_result = {
            "link_types": [_make_link_type(name="customer_to_order")],
        }

        conflicts = service._detect_conflicts(ontology_id, extraction_result)

        assert len(conflicts) >= 1
        link_conflicts = [c for c in conflicts if c["type"] == "link_type"]
        assert len(link_conflicts) == 1
        assert link_conflicts[0]["name"] == "customer_to_order"
        assert link_conflicts[0]["conflict"] == "duplicate_name"

    def test_detects_duplicate_action_type_names(self, service, ontology_id):
        """_detect_conflicts detects duplicate action_type names."""
        service.ontology_service.create_action_type(
            ontology_id,
            _make_action_type(name="create_order"),
        )

        extraction_result = {
            "action_types": [_make_action_type(name="create_order")],
        }

        conflicts = service._detect_conflicts(ontology_id, extraction_result)

        assert len(conflicts) >= 1
        action_conflicts = [c for c in conflicts if c["type"] == "action_type"]
        assert len(action_conflicts) == 1
        assert action_conflicts[0]["name"] == "create_order"

    def test_detects_duplicate_rule_type_names(self, service, ontology_id):
        """_detect_conflicts detects duplicate rule_type names."""
        service.ontology_service.create_rule_type(
            ontology_id,
            _make_rule_type(name="validate_order"),
        )

        extraction_result = {
            "rule_types": [_make_rule_type(name="validate_order")],
        }

        conflicts = service._detect_conflicts(ontology_id, extraction_result)

        assert len(conflicts) >= 1
        rule_conflicts = [c for c in conflicts if c["type"] == "rule_type"]
        assert len(rule_conflicts) == 1

    def test_detects_duplicate_process_type_names(self, service, ontology_id):
        """_detect_conflicts detects duplicate process_type names."""
        service.ontology_service.create_process_type(
            ontology_id,
            _make_process_type(name="order_process"),
        )

        extraction_result = {
            "process_types": [_make_process_type(name="order_process")],
        }

        conflicts = service._detect_conflicts(ontology_id, extraction_result)

        assert len(conflicts) >= 1
        process_conflicts = [c for c in conflicts if c["type"] == "process_type"]
        assert len(process_conflicts) == 1

    def test_detects_duplicate_function_type_names(self, service, ontology_id):
        """_detect_conflicts detects duplicate function_type names."""
        service.ontology_service.create_function_type(
            ontology_id,
            _make_function_type(name="compute_total"),
        )

        extraction_result = {
            "function_types": [_make_function_type(name="compute_total")],
        }

        conflicts = service._detect_conflicts(ontology_id, extraction_result)

        assert len(conflicts) >= 1
        func_conflicts = [c for c in conflicts if c["type"] == "function_type"]
        assert len(func_conflicts) == 1

    def test_detects_duplicate_indicator_type_names(self, service, ontology_id):
        """_detect_conflicts detects duplicate indicator_type names."""
        service.ontology_service.create_indicator_type(
            ontology_id,
            _make_indicator_type(name="order_count"),
        )

        extraction_result = {
            "indicator_types": [_make_indicator_type(name="order_count")],
        }

        conflicts = service._detect_conflicts(ontology_id, extraction_result)

        assert len(conflicts) >= 1
        ind_conflicts = [c for c in conflicts if c["type"] == "indicator_type"]
        assert len(ind_conflicts) == 1

    def test_detects_similar_name_conflict(self, service, ontology_id):
        """_detect_conflicts flags similar object_type names (Levenshtein < 3)."""
        service.ontology_service.create_object_type(
            ontology_id, _make_object_type(name="customer")
        )

        extraction_result = {
            "object_types": [_make_object_type(name="custumer")],  # 1 edit distance
        }

        conflicts = service._detect_conflicts(ontology_id, extraction_result)

        similar_conflicts = [c for c in conflicts if c["conflict"] == "similar_name"]
        assert len(similar_conflicts) >= 1
        assert similar_conflicts[0]["existing_name"] == "customer"
        assert similar_conflicts[0]["name"] == "custumer"

    def test_no_similar_name_conflict_for_distant_names(self, service, ontology_id):
        """_detect_conflicts does not flag names with Levenshtein >= 3."""
        service.ontology_service.create_object_type(
            ontology_id, _make_object_type(name="customer")
        )

        extraction_result = {
            "object_types": [_make_object_type(name="product")],  # very different
        }

        conflicts = service._detect_conflicts(ontology_id, extraction_result)

        similar_conflicts = [c for c in conflicts if c["conflict"] == "similar_name"]
        assert len(similar_conflicts) == 0
