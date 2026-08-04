"""Unit tests for TemplateEngine (data.hyper_extract.services.template_engine).

Tests cover:
- T021: list_presets() — dynamic enumeration via Template.list (no hardcoding)
- T022: assess() — settled check → pre-filter → trial_extract → score → sort
- T023: scoring formula — 0.3*norm(ec) + 0.3*norm(rc) + 0.2*fc + 0.2*td
- T029: settled template lightweight validation (500-char trial, score≥threshold*0.8)

All tests mock HEAdapter, SqliteTemplateStorage, and embedder — no real LLM calls.
"""

import math
from unittest.mock import MagicMock, patch, call

import pytest


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_preset_cfg(
    name="general/base_graph",
    description="通用知识图谱",
    type="graph",
    tags=None,
    language="zh",
):
    """Build a fake TemplateCfg dict as returned by Template.list()."""
    return {
        "name": name,
        "description": description,
        "type": type,
        "tags": tags or ["general", "graph"],
        "language": language,
    }


def _make_trial_result(entity_count=5, relation_count=3, field_coverage=0.8, type_diversity=0.6, types_found=None):
    """Build a fake trial_extract() return value."""
    return {
        "entity_count": entity_count,
        "relation_count": relation_count,
        "field_coverage": field_coverage,
        "type_diversity": type_diversity,
        "types_found": types_found or ["person", "org"],
    }


def _make_mock_adapter(with_template_list=True, trial_results=None):
    """Build a mock HEAdapter with _Template.list and trial_extract wired.

    Args:
        with_template_list: If True, _Template.list returns a dict of presets.
        trial_results: If provided, trial_extract side_effect or return_value.
    """
    adapter = MagicMock()
    adapter.is_available.return_value = True

    # _Template class with .list() static method
    template_cls = MagicMock()
    if with_template_list:
        presets = {
            "general/base_graph": _make_preset_cfg("general/base_graph", "通用知识图谱"),
            "general/concept_graph": _make_preset_cfg("general/concept_graph", "概念图谱"),
            "finance/earnings_summary": _make_preset_cfg("finance/earnings_summary", "财报摘要", type="model"),
            "legal/contract_obligation": _make_preset_cfg("legal/contract_obligation", "合同义务", type="graph"),
            "medicine/treatment_map": _make_preset_cfg("medicine/treatment_map", "治疗方案", type="graph"),
            "industry/equipment_topology": _make_preset_cfg("industry/equipment_topology", "设备拓扑", type="graph"),
        }
        template_cls.list.return_value = presets
    adapter._Template = template_cls

    # trial_extract
    if trial_results is None:
        trial_results = _make_trial_result()
    if isinstance(trial_results, list):
        adapter.trial_extract.side_effect = trial_results
    else:
        adapter.trial_extract.return_value = trial_results

    # _create_embedder returns a mock embedder
    embedder = MagicMock()
    embedder.embed_query.return_value = [0.1] * 128
    embedder.embed_documents.return_value = [[0.1] * 128 for _ in range(6)]
    adapter._create_embedder.return_value = embedder

    return adapter


# ---------------------------------------------------------------------------
# T021: list_presets()
# ---------------------------------------------------------------------------

class TestTemplateEngineListPresets:
    @pytest.fixture
    def engine(self):
        from odap.biz.data.hyper_extract.services.template_engine import TemplateEngine
        adapter = _make_mock_adapter()
        storage = MagicMock()
        return TemplateEngine(adapter, storage)

    def test_list_presets_calls_template_list_with_zh_filter(self, engine):
        engine.list_presets()
        engine._adapter._Template.list.assert_called_once()
        _, kwargs = engine._adapter._Template.list.call_args
        assert kwargs.get("filter_by_language") == "zh", \
            "Must call Template.list with filter_by_language='zh'"

    def test_list_presets_returns_list_of_dicts(self, engine):
        result = engine.list_presets()
        assert isinstance(result, list)
        assert len(result) == 6
        for item in result:
            assert isinstance(item, dict)

    def test_list_presets_parses_template_cfg_fields(self, engine):
        result = engine.list_presets()
        for item in result:
            assert "name" in item
            assert "description" in item
            assert "type" in item
            assert "tags" in item
            assert "language" in item

    def test_list_presets_returns_empty_list_when_no_presets(self, engine):
        engine._adapter._Template.list.return_value = {}
        result = engine.list_presets()
        assert result == []

    def test_list_presets_raises_runtime_error_when_he_unavailable(self, engine):
        engine._adapter.is_available.return_value = False
        with pytest.raises(RuntimeError, match="hyperextract"):
            engine.list_presets()

    def test_list_presets_does_not_hardcode(self, engine):
        """Verify presets come from Template.list(), not a hardcoded list."""
        # Add a new preset dynamically
        engine._adapter._Template.list.return_value = {
            "custom/new_template": _make_preset_cfg("custom/new_template", "动态新增"),
        }
        result = engine.list_presets()
        assert len(result) == 1
        assert result[0]["name"] == "custom/new_template"


# ---------------------------------------------------------------------------
# T022: assess()
# ---------------------------------------------------------------------------

class TestTemplateEngineAssess:
    @pytest.fixture
    def engine(self):
        """Engine with mocked adapter and storage.

        Iter 2.1: assess() no longer queries storage for settled templates
        (FR-017/FR-018 removed). The storage mock is retained for
        constructor compatibility but is not exercised by assess().
        """
        from odap.biz.data.hyper_extract.services.template_engine import TemplateEngine
        adapter = _make_mock_adapter()
        storage = MagicMock()
        return TemplateEngine(adapter, storage), adapter, storage

    def test_assess_always_runs_full_trial(self, engine):
        """Iter 2.1: assess() always runs full trial — no settled short-circuit."""
        eng, adapter, storage = engine
        result = eng.assess("some text", "ont-1")
        # No settled check → 5 full trial calls (top-k=5)
        assert adapter.trial_extract.call_count == 5
        assert result.get("settled_used") is False

    def test_assess_does_not_query_storage_for_settled(self, engine):
        """Iter 2.1: assess() must NOT call storage.get_by_ontology (FR-017/018 removed)."""
        eng, adapter, storage = engine
        eng.assess("some text", "ont-1")
        storage.get_by_ontology.assert_not_called()

    def test_assess_pre_filters_top_k(self, engine):
        eng, adapter, storage = engine
        # Verify embedder was used for pre-filtering
        result = eng.assess("some text", "ont-1")
        embedder = adapter._create_embedder.return_value
        # embed_query called for input text
        embedder.embed_query.assert_called_once_with("some text")
        # embed_documents called for preset descriptions
        embedder.embed_documents.assert_called_once()

    def test_assess_calls_trial_extract_for_top_k(self, engine):
        eng, adapter, storage = engine
        eng.assess("some text", "ont-1")
        # top-k=5 → trial_extract called 5 times
        assert adapter.trial_extract.call_count == 5

    def test_assess_returns_sorted_candidates_with_score(self, engine):
        eng, adapter, storage = engine
        result = eng.assess("some text", "ont-1")
        assert "candidates" in result
        assert isinstance(result["candidates"], list)
        # All candidates have score
        for cand in result["candidates"]:
            assert "score" in cand
            assert isinstance(cand["score"], (int, float))
        # Sorted descending by score
        scores = [c["score"] for c in result["candidates"]]
        assert scores == sorted(scores, reverse=True)

    def test_assess_returns_best_score_and_threshold(self, engine):
        eng, adapter, storage = engine
        result = eng.assess("some text", "ont-1")
        assert "best_score" in result
        assert "threshold" in result
        assert result["threshold"] == 0.5  # default

    def test_assess_sets_needs_custom_when_best_below_threshold(self, engine):
        eng, adapter, storage = engine
        # All trials return 0 metrics → score=0 → needs_custom=True
        adapter.trial_extract.return_value = _make_trial_result(
            entity_count=0, relation_count=0, field_coverage=0.0, type_diversity=0.0
        )
        result = eng.assess("some text", "ont-1")
        assert result["needs_custom"] is True
        assert result["best_score"] < result["threshold"]

    def test_assess_sets_needs_custom_false_when_best_above_threshold(self, engine):
        eng, adapter, storage = engine
        adapter.trial_extract.return_value = _make_trial_result(
            entity_count=10, relation_count=8, field_coverage=0.9, type_diversity=0.7
        )
        result = eng.assess("some text", "ont-1")
        assert result["needs_custom"] is False
        assert result["best_score"] >= result["threshold"]


# ---------------------------------------------------------------------------
# T023: scoring formula
# ---------------------------------------------------------------------------

class TestTemplateEngineScoring:
    @pytest.fixture
    def engine(self):
        from odap.biz.data.hyper_extract.services.template_engine import TemplateEngine
        adapter = _make_mock_adapter()
        storage = MagicMock()
        return TemplateEngine(adapter, storage)

    def test_score_formula_uses_correct_weights(self, engine):
        """Verify: score = 0.3*norm(ec) + 0.3*norm(rc) + 0.2*fc + 0.2*td"""
        # Single candidate: ec=10, rc=5, fc=0.8, td=0.6
        # norm(ec) = 10/10 = 1.0, norm(rc) = 5/5 = 1.0
        # score = 0.3*1.0 + 0.3*1.0 + 0.2*0.8 + 0.2*0.6 = 0.3 + 0.3 + 0.16 + 0.12 = 0.88
        trial = _make_trial_result(entity_count=10, relation_count=5, field_coverage=0.8, type_diversity=0.6)
        score = engine._compute_score(trial, max_ec=10, max_rc=5)
        assert abs(score - 0.88) < 0.001

    def test_score_normalization_by_max(self, engine):
        """Verify normalization divides by max across candidates."""
        # ec=5, max_ec=10 → norm=0.5
        # rc=2, max_rc=5 → norm=0.4
        # fc=0.8, td=0.6
        # score = 0.3*0.5 + 0.3*0.4 + 0.2*0.8 + 0.2*0.6 = 0.15 + 0.12 + 0.16 + 0.12 = 0.55
        trial = _make_trial_result(entity_count=5, relation_count=2, field_coverage=0.8, type_diversity=0.6)
        score = engine._compute_score(trial, max_ec=10, max_rc=5)
        assert abs(score - 0.55) < 0.001

    def test_score_threshold_comparison(self, engine):
        """Verify needs_custom is True when best_score < threshold."""
        # Low metrics → score should be below 0.5
        trial = _make_trial_result(entity_count=1, relation_count=0, field_coverage=0.2, type_diversity=0.1)
        score = engine._compute_score(trial, max_ec=10, max_rc=5)
        assert score < 0.5

    def test_score_zero_when_no_entities(self, engine):
        """Verify score=0 when entity_count=0."""
        trial = _make_trial_result(entity_count=0, relation_count=0, field_coverage=0.0, type_diversity=0.0)
        score = engine._compute_score(trial, max_ec=10, max_rc=5)
        assert score == 0.0

    def test_score_handles_zero_max_gracefully(self, engine):
        """Verify no division by zero when all candidates have 0 entities/relations."""
        trial = _make_trial_result(entity_count=0, relation_count=0, field_coverage=0.0, type_diversity=0.0)
        score = engine._compute_score(trial, max_ec=0, max_rc=0)
        assert score == 0.0

    def test_score_max_when_all_metrics_max(self, engine):
        """Verify score=1.0 when all metrics are maxed."""
        trial = _make_trial_result(entity_count=10, relation_count=5, field_coverage=1.0, type_diversity=1.0)
        score = engine._compute_score(trial, max_ec=10, max_rc=5)
        assert abs(score - 1.0) < 0.001


# ---------------------------------------------------------------------------
# T029: settled template lightweight validation — REMOVED in Iter 2.1
# FR-017/FR-018 (application-layer template sediment) superseded by
# persistent HE Knowledge Abstract (data/he_kb/{ws}/{ont}/).
# Settled validation tests removed: assess() always runs full pipeline.
# ---------------------------------------------------------------------------


# ---------------------------------------------------------------------------
# T030: generate_custom()
# ---------------------------------------------------------------------------

_VALID_YAML = """\
language: [zh]
name: custom_test_template
type: graph
tags: [custom, test]
description:
  zh: 自定义测试模板
  en: Custom test template
output:
  entities:
    fields:
      name: { type: str, required: true }
      type: { type: str, required: true }
      description: { type: str, required: false }
identifiers:
  entity_id: "{name}"
  relation_id: "{source}_{relation_type}_{target}"
  relation_members: [source, target]
"""

_INVALID_YAML = "this is not: valid: yaml: [[["


class TestTemplateEngineGenerateCustom:
    @pytest.fixture
    def engine(self):
        from odap.biz.data.hyper_extract.services.template_engine import TemplateEngine
        adapter = _make_mock_adapter()
        # LLM client mock
        llm_client = MagicMock()
        adapter._create_llm_client.return_value = llm_client
        storage = MagicMock()
        eng = TemplateEngine(adapter, storage)
        return eng, adapter, storage, llm_client

    def test_generate_custom_calls_llm_with_prompt(self, engine):
        eng, adapter, storage, llm_client = engine
        llm_response = MagicMock()
        llm_response.content = _VALID_YAML
        llm_client.invoke.return_value = llm_response
        adapter.trial_extract.return_value = _make_trial_result(
            entity_count=5, relation_count=3, field_coverage=0.8, type_diversity=0.6
        )

        eng.generate_custom("test text", {"object_types": []}, ["action", "rule"])

        llm_client.invoke.assert_called_once()
        # Verify prompt contains key elements
        _, kwargs = llm_client.invoke.call_args
        prompt = kwargs.get("prompt", "") or (llm_client.invoke.call_args.args[0] if llm_client.invoke.call_args.args else "")
        if not prompt:
            # May be passed as positional arg in a message list
            args = llm_client.invoke.call_args.args
            prompt = str(args[0]) if args else ""
        assert "yaml" in prompt.lower() or "yaml" in str(args).lower()

    def test_generate_custom_returns_valid_result(self, engine):
        eng, adapter, storage, llm_client = engine
        llm_response = MagicMock()
        llm_response.content = _VALID_YAML
        llm_client.invoke.return_value = llm_response
        adapter.trial_extract.return_value = _make_trial_result(
            entity_count=5, relation_count=3, field_coverage=0.8, type_diversity=0.6
        )

        result = eng.generate_custom("test text", {"object_types": []}, ["action"])

        assert result is not None
        assert "name" in result
        assert "yaml_content" in result
        assert "score" in result
        assert isinstance(result["score"], (int, float))

    def test_generate_custom_retries_on_failure(self, engine):
        eng, adapter, storage, llm_client = engine
        # First call returns invalid YAML, second returns valid
        bad_response = MagicMock()
        bad_response.content = _INVALID_YAML
        good_response = MagicMock()
        good_response.content = _VALID_YAML
        llm_client.invoke.side_effect = [bad_response, good_response]
        adapter.trial_extract.return_value = _make_trial_result(
            entity_count=5, relation_count=3, field_coverage=0.8, type_diversity=0.6
        )

        result = eng.generate_custom("test text", {"object_types": []}, ["action"])

        assert result is not None
        # LLM called at least 2 times (retry)
        assert llm_client.invoke.call_count >= 2

    def test_generate_custom_returns_none_if_all_retries_fail(self, engine):
        eng, adapter, storage, llm_client = engine
        bad_response = MagicMock()
        bad_response.content = _INVALID_YAML
        llm_client.invoke.return_value = bad_response

        result = eng.generate_custom("test text", {"object_types": []}, ["action"])

        assert result is None
        # Max 2 retries → 3 attempts total (1 initial + 2 retries)
        assert llm_client.invoke.call_count <= 3

    def test_generate_custom_validates_with_trial_extract(self, engine):
        eng, adapter, storage, llm_client = engine
        llm_response = MagicMock()
        llm_response.content = _VALID_YAML
        llm_client.invoke.return_value = llm_response
        adapter.trial_extract.return_value = _make_trial_result(
            entity_count=5, relation_count=3, field_coverage=0.8, type_diversity=0.6
        )

        eng.generate_custom("test text", {"object_types": []}, ["action"])

        # trial_extract should be called for validation
        adapter.trial_extract.assert_called()


# ---------------------------------------------------------------------------
# T031/T032/T033: settle_template / get_settled_template / drift detection
# — REMOVED in Iter 2.1 (ADR-074)
# FR-017/FR-018 application-layer template sediment superseded by persistent
# HE Knowledge Abstract (data/he_kb/{ws}/{ont}/). Drift detection no longer
# applies — assess() always runs the full pipeline.
# ---------------------------------------------------------------------------


# ---------------------------------------------------------------------------
# T037: custom generation degradation (EC-016)
# ---------------------------------------------------------------------------

class TestTemplateEngineCustomDegradation:
    @pytest.fixture
    def engine(self):
        from odap.biz.data.hyper_extract.services.template_engine import TemplateEngine
        adapter = _make_mock_adapter()
        llm_client = MagicMock()
        adapter._create_llm_client.return_value = llm_client
        storage = MagicMock()
        return TemplateEngine(adapter, storage), adapter, storage, llm_client

    def test_custom_generation_failure_sets_degradation_flag(self, engine):
        """EC-016: If generate_custom fails after retries, set degradation_flag."""
        eng, adapter, storage, llm_client = engine
        bad_response = MagicMock()
        bad_response.content = _INVALID_YAML
        llm_client.invoke.return_value = bad_response

        result = eng.generate_custom_with_fallback(
            "test text",
            {"object_types": []},
            ["action"],
            best_preset={"name": "general/base_graph", "score": 0.6},
        )

        # Should return best preset with degradation flag
        assert result is not None
        assert result.get("degradation_flag") == "custom_generation_failed"
        assert result["name"] == "general/base_graph"

    def test_custom_generation_success_no_degradation(self, engine):
        eng, adapter, storage, llm_client = engine
        good_response = MagicMock()
        good_response.content = _VALID_YAML
        llm_client.invoke.return_value = good_response
        adapter.trial_extract.return_value = _make_trial_result(
            entity_count=5, relation_count=3, field_coverage=0.8, type_diversity=0.6
        )

        result = eng.generate_custom_with_fallback(
            "test text",
            {"object_types": []},
            ["action"],
            best_preset={"name": "general/base_graph", "score": 0.6},
        )

        assert result is not None
        assert "degradation_flag" not in result or result.get("degradation_flag") is None
        assert "custom" in result.get("name", "").lower() or result.get("source") == "custom"


# ---------------------------------------------------------------------------
# T050: select_complementary() — greedy set cover
# ---------------------------------------------------------------------------

_ODAP_5_CATEGORIES = ["object", "relation", "action", "rule", "process"]


def _make_scored_candidate(
    name: str,
    score: float,
    entity_count: int = 0,
    relation_count: int = 0,
    types_found=None,
):
    """Build a fake scored candidate as returned by assess()."""
    return {
        "name": name,
        "score": score,
        "source": "preset",
        "description": f"Template {name}",
        "trial_result": _make_trial_result(
            entity_count=entity_count,
            relation_count=relation_count,
            types_found=types_found or [],
        ),
    }


class TestTemplateEngineSelectComplementary:
    """T050: Greedy set cover multi-template selection."""

    @pytest.fixture
    def engine(self):
        from odap.biz.data.hyper_extract.services.template_engine import TemplateEngine
        adapter = _make_mock_adapter()
        storage = MagicMock()
        return TemplateEngine(adapter, storage)

    def test_empty_candidates_returns_empty(self, engine):
        """No candidates → return empty list."""
        result = engine.select_complementary([], {"object_types": []})
        assert result == []

    def test_single_template_covers_all_returns_one(self, engine):
        """One template covering all 5 categories → return just that one."""
        candidate = _make_scored_candidate(
            "all_in_one",
            score=0.9,
            entity_count=10,
            relation_count=5,
            types_found=["person", "action", "rule", "process"],
        )
        result = engine.select_complementary([candidate], {"object_types": []})
        assert len(result) == 1
        assert result[0]["name"] == "all_in_one"
        assert set(result[0]["covers"]) == set(_ODAP_5_CATEGORIES)

    def test_single_template_covers_some_returns_one(self, engine):
        """One template covering only some categories → still return it (best effort)."""
        candidate = _make_scored_candidate(
            "objects_only",
            score=0.7,
            entity_count=5,
            relation_count=0,
            types_found=["person"],
        )
        result = engine.select_complementary([candidate], {"object_types": []})
        assert len(result) == 1
        assert "object" in result[0]["covers"]

    def test_two_templates_needed_to_cover_all(self, engine):
        """Two complementary templates needed → return both."""
        candidate_a = _make_scored_candidate(
            "base_graph",
            score=0.8,
            entity_count=10,
            relation_count=5,
            types_found=["person", "org"],
        )
        candidate_b = _make_scored_candidate(
            "action_rule",
            score=0.6,
            entity_count=3,
            relation_count=0,
            types_found=["action", "rule", "process"],
        )
        result = engine.select_complementary(
            [candidate_a, candidate_b], {"object_types": []}
        )
        assert len(result) == 2
        # Higher score first
        assert result[0]["name"] == "base_graph"
        assert result[1]["name"] == "action_rule"
        # Together they cover all 5
        all_covers = set()
        for r in result:
            all_covers.update(r["covers"])
        assert all_covers == set(_ODAP_5_CATEGORIES)

    def test_greedy_picks_highest_score_first(self, engine):
        """Greedy algorithm starts from highest scoring template."""
        candidates = [
            _make_scored_candidate("low", score=0.3, entity_count=1, types_found=["person"]),
            _make_scored_candidate("high", score=0.9, entity_count=10, relation_count=5, types_found=["org"]),
            _make_scored_candidate("mid", score=0.5, entity_count=3, types_found=["action"]),
        ]
        result = engine.select_complementary(candidates, {"object_types": []})
        # First selected should be highest score
        assert result[0]["name"] == "high"
        assert result[0]["score"] == 0.9

    def test_greedy_adds_best_covering_missing(self, engine):
        """After picking highest, add template covering most uncovered categories."""
        # Template A: high score, covers object+relation
        candidate_a = _make_scored_candidate(
            "a", score=0.9, entity_count=10, relation_count=5, types_found=[]
        )
        # Template B: mid score, covers action+rule
        candidate_b = _make_scored_candidate(
            "b", score=0.6, entity_count=2, relation_count=0, types_found=["action", "rule"]
        )
        # Template C: low score, covers process only
        candidate_c = _make_scored_candidate(
            "c", score=0.4, entity_count=1, relation_count=0, types_found=["process"]
        )
        result = engine.select_complementary(
            [candidate_a, candidate_b, candidate_c], {"object_types": []}
        )
        # A first (highest), then B (covers 2 missing), then C (covers 1 missing)
        assert len(result) == 3
        assert result[0]["name"] == "a"
        assert result[1]["name"] == "b"
        assert result[2]["name"] == "c"

    def test_candidates_exhausted_returns_partial(self, engine):
        """If candidates exhausted before covering all 5, return what we have."""
        candidate = _make_scored_candidate(
            "partial",
            score=0.7,
            entity_count=5,
            relation_count=2,
            types_found=["person"],
        )
        result = engine.select_complementary([candidate], {"object_types": []})
        assert len(result) == 1
        # Only covers object + relation, not all 5
        all_covers = set()
        for r in result:
            all_covers.update(r["covers"])
        assert "object" in all_covers
        assert "action" not in all_covers

    def test_result_has_covers_field(self, engine):
        """Each result item has a 'covers' list."""
        candidate = _make_scored_candidate(
            "test", score=0.8, entity_count=5, relation_count=3, types_found=["action"]
        )
        result = engine.select_complementary([candidate], {"object_types": []})
        assert len(result) == 1
        assert "covers" in result[0]
        assert isinstance(result[0]["covers"], list)

    def test_result_preserves_score(self, engine):
        """Score from candidate is preserved in result."""
        candidate = _make_scored_candidate(
            "test", score=0.75, entity_count=5, relation_count=3
        )
        result = engine.select_complementary([candidate], {"object_types": []})
        assert result[0]["score"] == 0.75

    def test_no_duplicate_templates_in_result(self, engine):
        """A template is only selected once."""
        candidate = _make_scored_candidate(
            "solo", score=0.9, entity_count=10, relation_count=5,
            types_found=["action", "rule", "process"]
        )
        result = engine.select_complementary([candidate], {"object_types": []})
        names = [r["name"] for r in result]
        assert len(names) == len(set(names))

    def test_redundant_template_not_added(self, engine):
        """Template covering only already-covered categories is not added."""
        candidate_a = _make_scored_candidate(
            "full", score=0.9, entity_count=10, relation_count=5,
            types_found=["action", "rule", "process"]
        )
        candidate_b = _make_scored_candidate(
            "redundant", score=0.5, entity_count=3, relation_count=1,
            types_found=["person"]
        )
        # candidate_a covers all 5 → candidate_b adds nothing new
        result = engine.select_complementary(
            [candidate_a, candidate_b], {"object_types": []}
        )
        assert len(result) == 1
        assert result[0]["name"] == "full"
