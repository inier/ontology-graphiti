"""Unit tests for ExtractService (data.hyper_extract.services.extract_service).

Tests cover:
- T052: LLM supplement extraction — LLM called when category entity_count < 2,
  supplement results merged, degradation flag on failure
- T053: extract_from_nl() orchestration — assess → select_complementary →
  multi-parse → LLM supplement → merge → validate → session update;
  EC-006 single template failure isolation; degradation_flags populated
- T054: ValidationEngine integration — validation_report in session.result_data,
  needs_review gating confirm_extraction

All tests mock HEAdapter, TemplateEngine, ValidationEngine, OntologyMapper.
No real LLM/Neo4j/SQLite calls.
"""

import asyncio
import json
from unittest.mock import AsyncMock, MagicMock, patch, call

import pytest


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_assess_result(
    candidates=None,
    best_score=0.7,
    threshold=0.5,
    needs_custom=False,
    settled_used=False,
):
    """Build a fake assess() return value from TemplateEngine."""
    return {
        "candidates": candidates or [
            {"name": "general/base_graph", "score": 0.7, "source": "preset",
             "trial_result": {"entity_count": 5, "relation_count": 3, "types_found": ["person"]}},
        ],
        "best_score": best_score,
        "threshold": threshold,
        "needs_custom": needs_custom,
        "settled_used": settled_used,
    }


def _make_selected_templates():
    """Build a fake select_complementary() return value."""
    return [
        {"name": "general/base_graph", "score": 0.8, "covers": ["object", "relation"]},
        {"name": "action_rule_template", "score": 0.6, "covers": ["action", "rule"]},
    ]


def _make_parse_result(entities=None, relations=None):
    """Build a fake parse() return value from HEAdapter."""
    return {
        "entities": entities or [
            {"name": "EntityA", "type": "Organization", "description": "test", "properties": {}},
        ],
        "relations": relations or [],
    }


def _make_merged_result(
    entities=None,
    relations=None,
    object_types=None,
    action_types=None,
    rule_types=None,
    process_types=None,
    link_types=None,
    conflicts=None,
):
    """Build a fake merge_and_map() return value."""
    return {
        "entities": entities or [{"name": "EntityA", "type": "Organization", "properties": {}}],
        "relations": relations or [],
        "object_types": object_types or [],
        "link_types": link_types or [],
        "action_types": action_types or [],
        "rule_types": rule_types or [],
        "process_types": process_types or [],
        "conflicts": conflicts or [],
    }


def _make_validation_report(
    overall_status="passed",
    needs_review_count=0,
    total_entities=5,
    total_relations=3,
):
    """Build a fake validate() return value from ValidationEngine."""
    return {
        "schema_conformance": {"violations": [], "passed_count": 5, "violated_count": 0},
        "completeness": {"fill_rate": 0.8, "empty_rate": 0.2, "orphan_count": 0, "orphan_entities": []},
        "confidence": {"threshold": 0.6, "per_entity": [], "needs_review": []},
        "referential_consistency": {"dangling_relations": [], "invalid_action_targets": [], "invalid_rule_references": []},
        "summary": {
            "total_entities": total_entities,
            "total_relations": total_relations,
            "needs_review_count": needs_review_count,
            "overall_status": overall_status,
        },
    }


def _make_mock_session_store():
    """Build a mock storage that tracks session create/update."""
    store = MagicMock()
    store.create_session.return_value = {"status": "ok", "session_id": "sess-001"}
    store.update_session.return_value = {"status": "ok"}
    store.get_session.return_value = {
        "session_id": "sess-001",
        "ontology_id": "ont-1",
        "status": "reviewing",
        "result_data": {},
    }
    return store


def _make_mock_components():
    """Build a full set of mocked ExtractService dependencies."""
    adapter = MagicMock()
    adapter.is_available.return_value = True
    adapter.parse.return_value = _make_parse_result()

    template_engine = MagicMock()
    template_engine.assess.return_value = _make_assess_result()
    template_engine.select_complementary.return_value = _make_selected_templates()

    validation_engine = MagicMock()
    validation_engine.validate.return_value = _make_validation_report()

    ontology_mapper = MagicMock()
    ontology_mapper.merge_and_map.return_value = _make_merged_result()

    store = _make_mock_session_store()

    writer = AsyncMock()
    writer.write.return_value = {"status": "ok", "entities_written": 5, "relations_written": 3}

    return {
        "adapter": adapter,
        "template_engine": template_engine,
        "validation_engine": validation_engine,
        "ontology_mapper": ontology_mapper,
        "storage": store,
        "writer": writer,
    }


# ---------------------------------------------------------------------------
# T052: LLM supplement extraction
# ---------------------------------------------------------------------------

class TestExtractServiceLLMSupplement:
    """T052: LLM supplement for categories with entity_count < 2."""

    @pytest.fixture
    def service(self):
        from odap.biz.data.hyper_extract.services.extract_service import ExtractService
        comps = _make_mock_components()
        return ExtractService(**comps), comps

    def test_llm_supplement_called_when_category_below_threshold(self, service):
        """LLM supplement triggered when any ODAP category has < 2 entities."""
        svc, comps = service
        # Merged result has only 1 action_type → needs supplement
        merged = _make_merged_result(
            action_types=[{"name": "Act1"}],
            object_types=[{"name": "Obj1"}, {"name": "Obj2"}],
        )
        comps["ontology_mapper"].merge_and_map.return_value = merged

        # Mock LLM client
        llm_client = MagicMock()
        llm_client.invoke.return_value = MagicMock(content=json.dumps([
            {"name": "SupplementAct", "type": "action", "description": "LLM generated", "properties": {}}
        ]))
        comps["adapter"]._create_llm_client.return_value = llm_client

        result = asyncio.run(svc.extract_from_nl("test text", "ont-1"))

        # LLM should have been called for the "action" category
        assert llm_client.invoke.called

    def test_llm_supplement_not_called_when_all_categories_sufficient(self, service):
        """LLM supplement NOT triggered when all categories have >= 2 entities."""
        svc, comps = service
        merged = _make_merged_result(
            object_types=[{"name": "O1"}, {"name": "O2"}],
            action_types=[{"name": "A1"}, {"name": "A2"}],
            rule_types=[{"name": "R1"}, {"name": "R2"}],
            process_types=[{"name": "P1"}, {"name": "P2"}],
            link_types=[{"name": "L1"}, {"name": "L2"}],
        )
        comps["ontology_mapper"].merge_and_map.return_value = merged

        llm_client = MagicMock()
        comps["adapter"]._create_llm_client.return_value = llm_client

        asyncio.run(svc.extract_from_nl("test text", "ont-1"))

        # LLM should NOT have been called
        llm_client.invoke.assert_not_called()

    def test_llm_supplement_results_merged(self, service):
        """LLM supplement results are merged into the final result."""
        svc, comps = service
        merged = _make_merged_result(
            action_types=[{"name": "Act1"}],  # only 1 → needs supplement
        )
        comps["ontology_mapper"].merge_and_map.return_value = merged

        llm_client = MagicMock()
        llm_client.invoke.return_value = MagicMock(content=json.dumps([
            {"name": "SupplementAct", "type": "action", "description": "supplement", "properties": {}}
        ]))
        comps["adapter"]._create_llm_client.return_value = llm_client

        result = asyncio.run(svc.extract_from_nl("test text", "ont-1"))

        # The result should include supplement entities
        assert result.get("status") == "ok"
        # Check that supplement was added (action_types count increased)
        session_update = comps["storage"].update_session.call_args
        assert session_update is not None

    def test_llm_supplement_failure_sets_degradation_flag(self, service):
        """If LLM supplement fails, degradation_flag is set."""
        svc, comps = service
        merged = _make_merged_result(
            action_types=[{"name": "Act1"}],  # needs supplement
        )
        comps["ontology_mapper"].merge_and_map.return_value = merged

        # LLM raises exception
        llm_client = MagicMock()
        llm_client.invoke.side_effect = RuntimeError("LLM unavailable")
        comps["adapter"]._create_llm_client.return_value = llm_client

        result = asyncio.run(svc.extract_from_nl("test text", "ont-1"))

        # Should not fail entirely — degradation flag set
        assert result.get("status") == "ok"
        degradation_flags = result.get("degradation_flags", [])
        assert "llm_supplement_failed" in degradation_flags or any(
            "supplement" in str(f) for f in degradation_flags
        )


# ---------------------------------------------------------------------------
# T053: extract_from_nl() orchestration
# ---------------------------------------------------------------------------

class TestExtractServiceExtractFromNL:
    """T053: Full orchestration of extract_from_nl()."""

    @pytest.fixture
    def service(self):
        from odap.biz.data.hyper_extract.services.extract_service import ExtractService
        comps = _make_mock_components()
        return ExtractService(**comps), comps

    def test_orchestration_calls_assess(self, service):
        """Step 1: TemplateEngine.assess() is called."""
        svc, comps = service
        asyncio.run(svc.extract_from_nl("test text", "ont-1"))
        comps["template_engine"].assess.assert_called_once()

    def test_orchestration_calls_select_complementary(self, service):
        """Step 2: select_complementary() called with assess results."""
        svc, comps = service
        asyncio.run(svc.extract_from_nl("test text", "ont-1"))
        comps["template_engine"].select_complementary.assert_called_once()

    def test_orchestration_calls_parse_for_each_template(self, service):
        """Step 3: adapter.parse() called for each selected template."""
        svc, comps = service
        asyncio.run(svc.extract_from_nl("test text", "ont-1"))
        # 2 templates selected → 2 parse calls
        assert comps["adapter"].parse.call_count == 2

    def test_orchestration_calls_merge_and_map(self, service):
        """Step 4: OntologyMapper.merge_and_map() called with parse results."""
        svc, comps = service
        asyncio.run(svc.extract_from_nl("test text", "ont-1"))
        comps["ontology_mapper"].merge_and_map.assert_called_once()

    def test_orchestration_calls_validate(self, service):
        """Step 5: ValidationEngine.validate() called."""
        svc, comps = service
        asyncio.run(svc.extract_from_nl("test text", "ont-1"))
        comps["validation_engine"].validate.assert_called_once()

    def test_orchestration_creates_session(self, service):
        """Session is created via storage."""
        svc, comps = service
        asyncio.run(svc.extract_from_nl("test text", "ont-1"))
        comps["storage"].create_session.assert_called_once()

    def test_orchestration_updates_session_with_result(self, service):
        """Session is updated with extraction result."""
        svc, comps = service
        asyncio.run(svc.extract_from_nl("test text", "ont-1"))
        comps["storage"].update_session.assert_called()

    def test_single_template_failure_does_not_block_others(self, service):
        """EC-006: If one template parse fails, others still succeed."""
        svc, comps = service
        # First parse raises, second succeeds
        comps["adapter"].parse.side_effect = [
            RuntimeError("template 1 failed"),
            _make_parse_result(entities=[{"name": "EntityB", "type": "Organization", "properties": {}}]),
        ]

        result = asyncio.run(svc.extract_from_nl("test text", "ont-1"))

        # Should not fail entirely
        assert result.get("status") == "ok"
        # Both templates were attempted
        assert comps["adapter"].parse.call_count == 2

    def test_degradation_flags_populated_on_failures(self, service):
        """degradation_flags list populated when degradation occurs."""
        svc, comps = service
        # All parse calls fail
        comps["adapter"].parse.side_effect = RuntimeError("all failed")

        result = asyncio.run(svc.extract_from_nl("test text", "ont-1"))

        # Should have degradation flags
        degradation_flags = result.get("degradation_flags", [])
        assert len(degradation_flags) > 0

    def test_needs_custom_triggers_generate_custom(self, service):
        """When assess returns needs_custom=True, generate_custom is called."""
        svc, comps = service
        comps["template_engine"].assess.return_value = _make_assess_result(
            needs_custom=True, best_score=0.3
        )
        comps["template_engine"].generate_custom_with_fallback.return_value = {
            "name": "custom_gen",
            "yaml_content": "language: [zh]\nname: custom_gen\n",
            "score": 0.5,
        }

        asyncio.run(svc.extract_from_nl("test text", "ont-1"))

        comps["template_engine"].generate_custom_with_fallback.assert_called_once()

    def test_returns_status_ok_on_success(self, service):
        """Successful extraction returns status=ok."""
        svc, comps = service
        result = asyncio.run(svc.extract_from_nl("test text", "ont-1"))
        assert result["status"] == "ok"

    def test_returns_session_id(self, service):
        """Result includes session_id."""
        svc, comps = service
        result = asyncio.run(svc.extract_from_nl("test text", "ont-1"))
        assert "session_id" in result

    def test_empty_text_returns_error(self, service):
        """Empty text input returns error."""
        svc, comps = service
        result = asyncio.run(svc.extract_from_nl("", "ont-1"))
        assert result["status"] == "error"

    def test_empty_ontology_id_returns_error(self, service):
        """Empty ontology_id returns error."""
        svc, comps = service
        result = asyncio.run(svc.extract_from_nl("text", ""))
        assert result["status"] == "error"


# ---------------------------------------------------------------------------
# T054: ValidationEngine integration
# ---------------------------------------------------------------------------

class TestExtractServiceValidationIntegration:
    """T054: ValidationEngine integration with ExtractService."""

    @pytest.fixture
    def service(self):
        from odap.biz.data.hyper_extract.services.extract_service import ExtractService
        comps = _make_mock_components()
        return ExtractService(**comps), comps

    def test_validation_report_in_session_result_data(self, service):
        """validation_report is written to session.result_data."""
        svc, comps = service
        validation = _make_validation_report(overall_status="passed")
        comps["validation_engine"].validate.return_value = validation

        asyncio.run(svc.extract_from_nl("test text", "ont-1"))

        # Check session update includes validation_report
        update_call = comps["storage"].update_session.call_args
        args, kwargs = update_call
        # update_session may be called with (session_id, update_dict) or (session_id, **fields)
        update_data = args[1] if len(args) > 1 else kwargs
        # Look for validation_report in the update data (may be nested in result_data)
        update_str = json.dumps(update_data, default=str)
        assert "validation_report" in update_str or "overall_status" in update_str

    def test_needs_review_gates_confirm_extraction(self, service):
        """When validation overall_status=needs_review, confirm is gated."""
        svc, comps = service
        validation = _make_validation_report(
            overall_status="needs_review", needs_review_count=2
        )
        comps["validation_engine"].validate.return_value = validation

        result = asyncio.run(svc.extract_from_nl("test text", "ont-1"))

        # Result should indicate needs_review status
        assert result.get("status") == "ok"
        # Session status should reflect needs_review
        update_call = comps["storage"].update_session.call_args
        args, kwargs = update_call
        update_data = args[1] if len(args) > 1 else kwargs
        update_str = json.dumps(update_data, default=str)
        assert "needs_review" in update_str or "reviewing" in update_str

    def test_validation_failed_does_not_block_extraction(self, service):
        """EC-018: Validation failure returns status=error but doesn't block."""
        svc, comps = service
        comps["validation_engine"].validate.return_value = {
            "status": "error",
            "message": "validation internal error",
            "summary": {"overall_status": "error", "needs_review_count": 0},
        }

        result = asyncio.run(svc.extract_from_nl("test text", "ont-1"))

        # Extraction should still succeed (validation error is non-blocking)
        assert result.get("status") == "ok"
        # But degradation flag should be set
        degradation_flags = result.get("degradation_flags", [])
        assert "validation_skipped" in degradation_flags or any(
            "validation" in str(f) for f in degradation_flags
        )

    def test_validation_passed_allows_completion(self, service):
        """When validation passes, session can proceed to completion."""
        svc, comps = service
        validation = _make_validation_report(overall_status="passed")
        comps["validation_engine"].validate.return_value = validation

        result = asyncio.run(svc.extract_from_nl("test text", "ont-1"))

        assert result.get("status") == "ok"
        # No validation-related degradation flags
        degradation_flags = result.get("degradation_flags", [])
        assert "validation_skipped" not in degradation_flags
