"""T060 [TDD] SuggestionService tests.

Tests for AI suggestion lifecycle management:
pending → accepted/rejected, audit log integration.
"""
import pytest


@pytest.fixture
def service(tmp_path):
    from odap.biz.core.ontology.assistant.services.suggestion_service import (
        SuggestionService,
    )
    db_path = str(tmp_path / "test_suggestion_service.db")
    return SuggestionService(db_path=db_path)


def _create_suggestion(service, **overrides):
    base = {
        "ontology_id": "ont-001",
        "target_type": "object_type",
        "target_id": "type-user-001",
        "suggestion_category": "add_property",
        "content": {"name": "email", "data_type": "STRING", "required": True},
        "source": "rule_engine",
        "confidence": 1.0,
    }
    base.update(overrides)
    return service.create_suggestion(base)


class TestCreateSuggestion:
    def test_create_returns_suggestion_with_id(self, service):
        result = service.create_suggestion({
            "ontology_id": "ont-001",
            "target_type": "object_type",
            "target_id": "type-001",
            "suggestion_category": "add_property",
            "content": {"name": "email"},
            "source": "rule_engine",
            "confidence": 1.0,
        })
        assert "suggestion_id" in result
        assert result["status"] == "pending"
        assert result["ontology_id"] == "ont-001"

    def test_create_missing_required_field_returns_error(self, service):
        result = service.create_suggestion({
            "target_type": "object_type",
            "suggestion_category": "add_property",
            "content": {},
            "source": "rule_engine",
        })
        assert result.get("status") == "error"


class TestGetSuggestion:
    def test_get_existing_suggestion(self, service):
        created = _create_suggestion(service)
        sid = created["suggestion_id"]
        result = service.get_suggestion(sid)
        assert result is not None
        assert result["suggestion_id"] == sid

    def test_get_nonexistent_returns_error(self, service):
        result = service.get_suggestion("nonexistent")
        assert result.get("status") == "error"


class TestListSuggestions:
    def test_list_by_ontology(self, service):
        _create_suggestion(service, ontology_id="ont-A")
        _create_suggestion(service, ontology_id="ont-A")
        _create_suggestion(service, ontology_id="ont-B")
        result = service.list_suggestions(ontology_id="ont-A")
        assert result["count"] == 2

    def test_list_by_status(self, service):
        _create_suggestion(service)
        created = _create_suggestion(service)
        service.accept_suggestion(created["suggestion_id"], user_id="u1")
        result = service.list_suggestions(status="pending")
        assert result["count"] == 1
        result2 = service.list_suggestions(status="accepted")
        assert result2["count"] == 1


class TestAcceptSuggestion:
    def test_accept_changes_status_to_accepted(self, service):
        created = _create_suggestion(service)
        sid = created["suggestion_id"]
        result = service.accept_suggestion(sid, user_id="user-001")
        assert result["status"] == "accepted"
        assert result.get("applied") is True

    def test_accept_nonexistent_returns_error(self, service):
        result = service.accept_suggestion("nonexistent", user_id="u1")
        assert result.get("status") == "error"

    def test_accept_already_accepted_returns_error(self, service):
        created = _create_suggestion(service)
        sid = created["suggestion_id"]
        service.accept_suggestion(sid, user_id="u1")
        result = service.accept_suggestion(sid, user_id="u1")
        assert result.get("status") == "error"


class TestRejectSuggestion:
    def test_reject_changes_status_to_rejected(self, service):
        created = _create_suggestion(service)
        sid = created["suggestion_id"]
        result = service.reject_suggestion(sid, user_id="user-001", reason="already exists")
        assert result["status"] == "rejected"
        assert result["rejection_reason"] == "already exists"

    def test_reject_without_reason(self, service):
        created = _create_suggestion(service)
        sid = created["suggestion_id"]
        result = service.reject_suggestion(sid, user_id="user-001")
        assert result["status"] == "rejected"

    def test_reject_nonexistent_returns_error(self, service):
        result = service.reject_suggestion("nonexistent", user_id="u1")
        assert result.get("status") == "error"


class TestDeleteSuggestion:
    def test_delete_existing(self, service):
        created = _create_suggestion(service)
        sid = created["suggestion_id"]
        result = service.delete_suggestion(sid)
        assert result["status"] == "deleted"

    def test_delete_nonexistent_returns_error(self, service):
        result = service.delete_suggestion("nonexistent")
        assert result.get("status") == "error"


class TestNamingConventionValidation:
    def test_valid_snake_case_accepted(self, service):
        result = service.validate_property_name("user_email")
        assert result["valid"] is True

    def test_invalid_camel_case_rejected(self, service):
        result = service.validate_property_name("userEmail")
        assert result["valid"] is False

    def test_invalid_with_spaces_rejected(self, service):
        result = service.validate_property_name("user email")
        assert result["valid"] is False

    def test_invalid_with_chinese_rejected(self, service):
        result = service.validate_property_name("用户邮箱")
        assert result["valid"] is False

    def test_reserved_word_rejected(self, service):
        result = service.validate_property_name("class")
        assert result["valid"] is False

    def test_empty_string_rejected(self, service):
        result = service.validate_property_name("")
        assert result["valid"] is False
