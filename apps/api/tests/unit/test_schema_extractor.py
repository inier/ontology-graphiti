"""Unit tests for SchemaLevelExtractor.

Covers:
- _normalize_result: valid data, missing fields, empty dict
- _parse_llm_response: valid JSON, JSON in markdown code block, invalid JSON
- extract_from_text: async method (skipped if LLM unavailable)
- _web_search: auto_search disabled, search failure handling
"""

import json
import types
import sys
import os
import pytest
from unittest.mock import AsyncMock, MagicMock, patch

# ---------------------------------------------------------------------------
# Handle optional graphiti_core dependency
# ---------------------------------------------------------------------------
try:
    import graphiti_core  # noqa: F401
except ImportError:
    gc = types.ModuleType("graphiti_core")
    gc_llm_client = types.ModuleType("graphiti_core.llm_client")
    gc_llm_config = types.ModuleType("graphiti_core.llm_client.config")
    gc_llm_openai = types.ModuleType("graphiti_core.llm_client.openai_client")
    gc_prompts = types.ModuleType("graphiti_core.prompts")
    gc_prompts_models = types.ModuleType("graphiti_core.prompts.models")

    gc_llm_config.LLMConfig = type("LLMConfig", (), {})
    gc_llm_config.ModelSize = type("ModelSize", (), {"medium": "medium"})
    gc_llm_openai.OpenAIClient = type("OpenAIClient", (), {
        "__init__": lambda self, *a, **kw: None,
    })
    # Message 必须接受 role= 和 content= 关键字参数
    gc_prompts_models.Message = lambda **kwargs: MagicMock(**kwargs)

    sys.modules["graphiti_core"] = gc
    sys.modules["graphiti_core.llm_client"] = gc_llm_client
    sys.modules["graphiti_core.llm_client.config"] = gc_llm_config
    sys.modules["graphiti_core.llm_client.openai_client"] = gc_llm_openai
    sys.modules["graphiti_core.prompts"] = gc_prompts
    sys.modules["graphiti_core.prompts.models"] = gc_prompts_models

# Try importing SchemaLevelExtractor; skip entire module if unavailable
try:
    from odap.biz.core.ontology.extraction.services.schema_extractor import (
        SchemaLevelExtractor,
    )
except Exception as _e:
    pytest.skip(
        f"SchemaLevelExtractor import failed: {_e}", allow_module_level=True
    )


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture(autouse=True)
def _ensure_graphiti_message_mock():
    """确保 graphiti_core.prompts.models.Message mock 能接受关键字参数。

    其他测试文件可能覆盖了 sys.modules 中的 graphiti_core mock，
    导致 Message() 不接受 role=/content= 参数。此 fixture 在每个测试前
    强制修复 Message mock。
    """
    if "graphiti_core.prompts.models" in sys.modules:
        sys.modules["graphiti_core.prompts.models"].Message = lambda **kwargs: MagicMock(**kwargs)


@pytest.fixture
def extractor():
    """Create a SchemaLevelExtractor instance for testing."""
    return SchemaLevelExtractor()


def _make_full_data():
    """Build a complete extraction result dict with all type lists populated."""
    return {
        "object_types": [
            {
                "name": "organization_unit",
                "display_name": "军事单位",
                "description": "An organizational unit",
                "properties": [
                    {
                        "name": "unit_name",
                        "property_type": "string",
                        "required": True,
                    }
                ],
                "classification_level": "S",
            }
        ],
        "link_types": [
            {
                "name": "commands",
                "source_type": "organization_unit",
                "target_type": "organization_unit",
                "cardinality": "1:N",
                "link_type": "COMPOSITION",
                "description": "Command hierarchy",
            }
        ],
        "action_types": [
            {
                "name": "deploy",
                "target_object_type": "organization_unit",
                "description": "Deploy unit",
                "parameters": [
                    {
                        "name": "location",
                        "param_type": "string",
                        "required": True,
                    }
                ],
            }
        ],
        "rule_types": [
            {
                "name": "max_command_depth",
                "condition": "Command depth > 5",
                "consequence": "Reject deployment",
                "priority": "high",
            }
        ],
        "process_types": [
            {
                "name": "deployment_process",
                "display_name": "部署流程",
                "description": "Standard deployment",
                "related_objects": ["organization_unit"],
            }
        ],
        "indicator_types": [
            {
                "name": "readiness_score",
                "indicator_type": "kpi",
                "formula": "weighted average of sub-unit readiness",
                "unit": "percentage",
            }
        ],
    }


# ---------------------------------------------------------------------------
# TestNormalizeResult
# ---------------------------------------------------------------------------

class TestNormalizeResult:
    """Tests for SchemaLevelExtractor._normalize_result."""

    def test_valid_result_with_all_fields(self, extractor):
        """A fully populated dict should be normalized with status='ok' and correct counts."""
        data = _make_full_data()
        result = extractor._normalize_result(data)

        assert result["status"] == "ok"
        assert len(result["object_types"]) == 1
        assert len(result["link_types"]) == 1
        assert len(result["action_types"]) == 1
        assert len(result["rule_types"]) == 1
        assert len(result["process_types"]) == 1
        assert len(result["indicator_types"]) == 1
        # summary counts
        assert result["summary"]["object_types"] == 1
        assert result["summary"]["link_types"] == 1
        assert result["summary"]["action_types"] == 1
        assert result["summary"]["rule_types"] == 1
        assert result["summary"]["process_types"] == 1
        assert result["summary"]["indicator_types"] == 1

    def test_missing_fields_get_defaults(self, extractor):
        """Fields absent from input should default to empty lists and zero counts."""
        data = {"object_types": [{"name": "x"}]}
        result = extractor._normalize_result(data)

        assert result["status"] == "ok"
        assert result["object_types"] == [{"name": "x"}]
        assert result["link_types"] == []
        assert result["action_types"] == []
        assert result["rule_types"] == []
        assert result["process_types"] == []
        assert result["indicator_types"] == []
        # summary
        assert result["summary"]["object_types"] == 1
        assert result["summary"]["link_types"] == 0
        assert result["summary"]["action_types"] == 0
        assert result["summary"]["rule_types"] == 0
        assert result["summary"]["process_types"] == 0
        assert result["summary"]["indicator_types"] == 0

    def test_empty_dict(self, extractor):
        """An empty input dict should produce all-empty lists and zero counts."""
        result = extractor._normalize_result({})

        assert result["status"] == "ok"
        assert result["object_types"] == []
        assert result["link_types"] == []
        assert result["action_types"] == []
        assert result["rule_types"] == []
        assert result["process_types"] == []
        assert result["indicator_types"] == []
        for key in ("object_types", "link_types", "action_types",
                     "rule_types", "process_types", "indicator_types"):
            assert result["summary"][key] == 0

    def test_function_types_included(self, extractor):
        """function_types should be present even though the LLM prompt does not request it."""
        data = {"function_types": [{"name": "calc_risk"}]}
        result = extractor._normalize_result(data)

        assert result["function_types"] == [{"name": "calc_risk"}]

    def test_multiple_items_counted_correctly(self, extractor):
        """Summary counts must reflect the actual number of items in each list."""
        data = {
            "object_types": [{"name": "a"}, {"name": "b"}, {"name": "c"}],
            "link_types": [{"name": "l1"}],
        }
        result = extractor._normalize_result(data)

        assert result["summary"]["object_types"] == 3
        assert result["summary"]["link_types"] == 1
        assert result["summary"]["action_types"] == 0


# ---------------------------------------------------------------------------
# TestParseLLMResponse
# ---------------------------------------------------------------------------

class TestParseLLMResponse:
    """Tests for SchemaLevelExtractor._parse_llm_response."""

    def test_valid_json(self, extractor):
        """A plain JSON string should be parsed and normalized."""
        payload = json.dumps({
            "object_types": [{"name": "asset"}],
            "link_types": [],
        })
        result = extractor._parse_llm_response(payload)

        assert result["status"] == "ok"
        assert result["object_types"] == [{"name": "asset"}]
        assert result["link_types"] == []

    def test_json_in_markdown_code_block_with_language(self, extractor):
        """JSON wrapped in ```json ... ``` should be extracted and parsed."""
        payload = '```json\n{"object_types": [{"name": "sensor"}]}\n```'
        result = extractor._parse_llm_response(payload)

        assert result["status"] == "ok"
        assert result["object_types"] == [{"name": "sensor"}]

    def test_json_in_markdown_code_block_without_language(self, extractor):
        """JSON wrapped in ``` ... ``` (no language tag) should be extracted."""
        payload = '```\n{"object_types": [{"name": "sensor"}]}\n```'
        result = extractor._parse_llm_response(payload)

        assert result["status"] == "ok"
        assert result["object_types"] == [{"name": "sensor"}]

    def test_invalid_json_returns_error(self, extractor):
        """Completely invalid JSON should return an error result."""
        result = extractor._parse_llm_response("this is not json at all")

        assert result["status"] == "error"
        assert "message" in result

    def test_json_embedded_in_text(self, extractor):
        """JSON embedded within surrounding text should be found by the regex fallback."""
        payload = 'Here is the result:\n{"object_types": [{"name": "target"}]}\nEnd of result.'
        result = extractor._parse_llm_response(payload)

        assert result["status"] == "ok"
        assert result["object_types"] == [{"name": "target"}]

    def test_broken_json_object_returns_error(self, extractor):
        """A string that contains a curly brace but is not valid JSON should return error."""
        result = extractor._parse_llm_response("{broken json content")

        assert result["status"] == "error"
        assert "message" in result

    def test_whitespace_only_returns_error(self, extractor):
        """Whitespace-only input should return an error result."""
        result = extractor._parse_llm_response("   \n\t  ")

        assert result["status"] == "error"
        assert "message" in result

    def test_full_data_roundtrip(self, extractor):
        """A full extraction result serialized to JSON should round-trip correctly."""
        data = _make_full_data()
        payload = json.dumps(data)
        result = extractor._parse_llm_response(payload)

        assert result["status"] == "ok"
        assert len(result["object_types"]) == 1
        assert result["object_types"][0]["name"] == "organization_unit"
        assert result["summary"]["object_types"] == 1
        assert result["summary"]["link_types"] == 1


# ---------------------------------------------------------------------------
# TestExtractFromText (requires LLM API -- skipped if unavailable)
# ---------------------------------------------------------------------------

class TestExtractFromText:
    """Tests for SchemaLevelExtractor.extract_from_text (async).

    These tests mock the LLM client to avoid requiring a real API key.
    """

    @pytest.mark.asyncio
    async def test_returns_error_when_api_key_missing(self, extractor):
        """extract_from_text should return an error dict when OPENAI_API_KEY is not set."""
        with patch.dict(os.environ, {}, clear=False):
            # Ensure no API key is set
            os.environ.pop("OPENAI_API_KEY", None)
            # Reset cached client so it tries to create a new one
            extractor._llm_client = None

            result = await extractor.extract_from_text("test domain description")
            assert result["status"] == "error"
            assert "OPENAI_API_KEY" in result["message"] or "API" in result["message"]

    @pytest.mark.asyncio
    async def test_returns_normalized_result_on_dict_response(self, extractor):
        """When LLM returns a dict, it should be normalized and returned."""
        mock_client = MagicMock()
        mock_data = _make_full_data()
        mock_client._generate_response = AsyncMock(return_value=(mock_data, None, None))

        extractor._llm_client = mock_client

        with patch.dict(os.environ, {"OPENAI_API_KEY": "test-key"}):
            result = await extractor.extract_from_text("military domain")

        assert result["status"] == "ok"
        assert len(result["object_types"]) == 1
        assert result["summary"]["object_types"] == 1

    @pytest.mark.asyncio
    async def test_parses_string_response_via_parse_llm_response(self, extractor):
        """When LLM returns a string, it should be parsed via _parse_llm_response."""
        mock_client = MagicMock()
        json_str = json.dumps({"object_types": [{"name": "vehicle"}]})
        mock_client._generate_response = AsyncMock(return_value=(json_str, None, None))

        extractor._llm_client = mock_client

        with patch.dict(os.environ, {"OPENAI_API_KEY": "test-key"}):
            result = await extractor.extract_from_text("transport domain")

        assert result["status"] == "ok"
        assert result["object_types"] == [{"name": "vehicle"}]

    @pytest.mark.asyncio
    async def test_unexpected_response_type_returns_error(self, extractor):
        """When LLM returns an unexpected type, an error should be returned."""
        mock_client = MagicMock()
        mock_client._generate_response = AsyncMock(return_value=(42, None, None))

        extractor._llm_client = mock_client

        with patch.dict(os.environ, {"OPENAI_API_KEY": "test-key"}):
            result = await extractor.extract_from_text("test domain")

        assert result["status"] == "error"
        assert "Unexpected" in result["message"]

    @pytest.mark.asyncio
    async def test_timeout_returns_error(self, extractor):
        """When LLM call times out, an error should be returned."""
        import asyncio

        mock_client = MagicMock()

        async def slow_response(*args, **kwargs):
            await asyncio.sleep(120)

        mock_client._generate_response = slow_response
        extractor._llm_client = mock_client

        with patch.dict(os.environ, {"OPENAI_API_KEY": "test-key"}):
            result = await extractor.extract_from_text("test domain")

        assert result["status"] == "error"
        assert "timed out" in result["message"].lower()

    @pytest.mark.asyncio
    async def test_auto_search_injects_context(self, extractor):
        """When auto_search=True, _web_search should be called and its result
        injected into the prompt."""
        mock_client = MagicMock()
        mock_data = {"object_types": []}
        mock_client._generate_response = AsyncMock(return_value=(mock_data, None, None))

        extractor._llm_client = mock_client

        with patch.dict(os.environ, {"OPENAI_API_KEY": "test-key"}):
            with patch.object(
                extractor, "_web_search", new_callable=AsyncMock, return_value="extra info"
            ) as mock_search:
                result = await extractor.extract_from_text("domain", auto_search=True)

        mock_search.assert_awaited_once_with("domain")
        assert result["status"] == "ok"


# ---------------------------------------------------------------------------
# TestWebSearch
# ---------------------------------------------------------------------------

class TestWebSearch:
    """Tests for SchemaLevelExtractor._web_search."""

    @pytest.mark.asyncio
    async def test_returns_empty_when_news_ingester_not_available(self, extractor):
        """When NewsIngester cannot be imported, _web_search should return empty string
        without raising."""
        # The real _web_search already catches import errors internally.
        result = await extractor._web_search("some query")
        assert result == ""

    @pytest.mark.asyncio
    async def test_successful_search_returns_content(self, extractor):
        """When NewsIngester.search succeeds, _web_search should return joined content."""
        mock_ingester = MagicMock()
        mock_ingester.search.return_value = [
            {"content": "Result 1"},
            {"content": "Result 2"},
            {"title": "Result 3 title"},
        ]

        # Patch the import inside _web_search to use our mock
        mock_module = MagicMock()
        mock_module.NewsIngester = MagicMock(return_value=mock_ingester)

        with patch.dict(
            "sys.modules",
            {"odap.biz.data.knowledge_base.ingestion.news_ingester": mock_module},
        ):
            result = await extractor._web_search("military domain")

        # Should contain content from the search results
        assert "Result 1" in result
        assert "Result 2" in result

    @pytest.mark.asyncio
    async def test_search_exception_returns_empty(self, extractor):
        """When NewsIngester.search raises an exception, _web_search returns empty string."""
        mock_ingester = MagicMock()
        mock_ingester.search.side_effect = RuntimeError("Search service down")

        mock_module = MagicMock()
        mock_module.NewsIngester = MagicMock(return_value=mock_ingester)

        with patch.dict(
            "sys.modules",
            {"odap.biz.data.knowledge_base.ingestion.news_ingester": mock_module},
        ):
            result = await extractor._web_search("query that triggers error")

        assert result == ""

    @pytest.mark.asyncio
    async def test_search_with_no_results_returns_empty(self, extractor):
        """When NewsIngester.search returns empty list, _web_search returns empty string."""
        mock_ingester = MagicMock()
        mock_ingester.search.return_value = []

        mock_module = MagicMock()
        mock_module.NewsIngester = MagicMock(return_value=mock_ingester)

        with patch.dict(
            "sys.modules",
            {"odap.biz.data.knowledge_base.ingestion.news_ingester": mock_module},
        ):
            result = await extractor._web_search("obscure query")

        assert result == ""
