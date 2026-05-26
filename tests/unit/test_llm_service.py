import pytest
import sys
import os
import types
from unittest.mock import MagicMock

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..', '..'))

_zhipu_skip = None
_v2_skip = None

try:
    import graphiti_core
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
    gc_prompts_models.Message = type("Message", (), {})

    sys.modules["graphiti_core"] = gc
    sys.modules["graphiti_core.llm_client"] = gc_llm_client
    sys.modules["graphiti_core.llm_client.config"] = gc_llm_config
    sys.modules["graphiti_core.llm_client.openai_client"] = gc_llm_openai
    sys.modules["graphiti_core.prompts"] = gc_prompts
    sys.modules["graphiti_core.prompts.models"] = gc_prompts_models

try:
    from odap.infra.llm.llm_service import ZhipuAIClient
except Exception as _e:
    _zhipu_skip = str(_e)

try:
    from odap.infra.openharness.v2_adapter import (
        AgentAction,
        AgentObservation,
        OpenHarnessIntegration,
        get_openharness_integration,
    )
except Exception as _e:
    _v2_skip = str(_e)

if _zhipu_skip:
    pytest.skip(f"ZhipuAIClient import failed: {_zhipu_skip}", allow_module_level=True)

if _v2_skip:
    pytest.skip(f"v2_adapter import failed: {_v2_skip}", allow_module_level=True)


@pytest.fixture
def client():
    return ZhipuAIClient(config=None)


class TestExtractJson:

    def test_direct_json_string(self, client):
        content = '{"name": "test", "value": 42}'
        result = client._extract_json(content)
        assert result == {"name": "test", "value": 42}

    def test_markdown_code_block_json(self, client):
        content = '```json\n{"name": "test", "value": 42}\n```'
        result = client._extract_json(content)
        assert result == {"name": "test", "value": 42}

    def test_markdown_code_block_no_language(self, client):
        content = '```\n{"name": "test", "value": 42}\n```'
        result = client._extract_json(content)
        assert result == {"name": "test", "value": 42}

    def test_response_wrapper_dict(self, client):
        content = '{"response": {"name": "inner", "count": 1}}'
        result = client._extract_json(content)
        assert result == {"name": "inner", "count": 1}

    def test_response_wrapper_string(self, client):
        content = '{"response": "{\\"name\\": \\"inner\\"}"}'
        result = client._extract_json(content)
        assert result == {"name": "inner"}

    def test_response_wrapper_array(self, client):
        content = '{"response": [1, 2, 3]}'
        result = client._extract_json(content)
        assert result == {"extracted_entities": [1, 2, 3]}

    def test_pure_array(self, client):
        content = '[1, 2, 3]'
        result = client._extract_json(content)
        assert result == {"extracted_entities": [1, 2, 3]}

    def test_invalid_json_returns_response(self, client):
        content = 'this is not json at all'
        result = client._extract_json(content)
        assert result == {"response": "this is not json at all"}

    def test_empty_string(self, client):
        content = ''
        result = client._extract_json(content)
        assert result == {"response": ""}

    def test_markdown_code_block_array(self, client):
        content = '```json\n[1, 2, 3]\n```'
        result = client._extract_json(content)
        assert result == {"extracted_entities": [1, 2, 3]}

    def test_json_embedded_in_text(self, client):
        content = 'Here is the result: {"name": "test"} end'
        result = client._extract_json(content)
        assert result == {"name": "test"}


class TestFuzzyMatchField:

    def test_exact_alias_match(self, client):
        properties = {"name": {}, "value": {}}
        result = client._fuzzy_match_field("entity_name", properties)
        assert result == "name"

    def test_exact_alias_entity_type(self, client):
        properties = {"entity_type_id": {}, "name": {}}
        result = client._fuzzy_match_field("type", properties)
        assert result == "entity_type_id"

    def test_exact_alias_source_node(self, client):
        properties = {"source": {}, "target": {}}
        result = client._fuzzy_match_field("source_node", properties)
        assert result == "source"

    def test_exact_alias_fact(self, client):
        properties = {"content": {}, "name": {}}
        result = client._fuzzy_match_field("fact", properties)
        assert result == "content"

    def test_containment_match(self, client):
        properties = {"entity_type_id": {}}
        result = client._fuzzy_match_field("entity_type", properties)
        assert result == "entity_type_id"

    def test_underscore_token_overlap(self, client):
        properties = {"target_node_id": {}}
        result = client._fuzzy_match_field("node_target", properties)
        assert result == "target_node_id"

    def test_no_match_returns_none(self, client):
        properties = {"name": {}, "value": {}}
        result = client._fuzzy_match_field("completely_unrelated_xyz", properties)
        assert result is None

    def test_dash_and_space_normalization(self, client):
        properties = {"entity_type_id": {}}
        result = client._fuzzy_match_field("entity-type", properties)
        assert result == "entity_type_id"


class TestCoerceType:

    def test_str_to_int(self, client):
        result = client._coerce_type("42", {"type": "integer"}, "field")
        assert result == 42

    def test_str_to_int_invalid(self, client):
        result = client._coerce_type("not_a_number", {"type": "integer"}, "field")
        assert result == 0

    def test_str_to_float(self, client):
        result = client._coerce_type("3.14", {"type": "number"}, "field")
        assert result == 3.14

    def test_str_to_float_invalid(self, client):
        result = client._coerce_type("not_a_float", {"type": "number"}, "field")
        assert result == 0.0

    def test_int_to_str(self, client):
        result = client._coerce_type(42, {"type": "string"}, "field")
        assert result == "42"

    def test_float_to_str(self, client):
        result = client._coerce_type(3.14, {"type": "string"}, "field")
        assert result == "3.14"

    def test_no_coercion_needed(self, client):
        result = client._coerce_type(42, {"type": "integer"}, "field")
        assert result is None

    def test_none_value(self, client):
        result = client._coerce_type(None, {"type": "integer"}, "field")
        assert result is None

    def test_anyof_non_null_type(self, client):
        schema = {"anyOf": [{"type": "integer"}, {"type": "null"}]}
        result = client._coerce_type("7", schema, "field")
        assert result == 7


class TestAgentDataModels:

    def test_agent_action_to_dict(self):
        action = AgentAction(
            tool_name="query_entities",
            params={"query": "test"},
            thought="need to query",
        )
        d = action.to_dict()
        assert d["tool_name"] == "query_entities"
        assert d["params"] == {"query": "test"}
        assert d["thought"] == "need to query"

    def test_agent_action_default_params(self):
        action = AgentAction(tool_name="end_mission")
        d = action.to_dict()
        assert d["tool_name"] == "end_mission"
        assert d["params"] == {}
        assert d["thought"] == ""

    def test_agent_observation_to_dict(self):
        obs = AgentObservation(
            state="active",
            tools_available=["tool_a", "tool_b"],
            last_result={"status": "success"},
            episode_history=[{"step": 1}],
        )
        d = obs.to_dict()
        assert d["state"] == "active"
        assert d["tools_available"] == ["tool_a", "tool_b"]
        assert d["last_result"] == {"status": "success"}
        assert d["episode_history"] == [{"step": 1}]

    def test_agent_observation_defaults(self):
        obs = AgentObservation(
            state="completed",
            tools_available=[],
        )
        d = obs.to_dict()
        assert d["state"] == "completed"
        assert d["tools_available"] == []
        assert d["last_result"] is None
        assert d["episode_history"] == []


class TestOpenHarnessIntegration:

    def test_singleton_pattern(self):
        OpenHarnessIntegration._instance = None
        a = OpenHarnessIntegration()
        b = OpenHarnessIntegration()
        assert a is b
        OpenHarnessIntegration._instance = None

    def test_get_openharness_integration_returns_instance(self):
        OpenHarnessIntegration._instance = None
        from odap.infra.openharness import v2_adapter
        v2_adapter._integration_instance = None
        inst = get_openharness_integration()
        assert isinstance(inst, OpenHarnessIntegration)
        inst2 = get_openharness_integration()
        assert inst is inst2
        OpenHarnessIntegration._instance = None
        v2_adapter._integration_instance = None

    def test_get_status_without_init(self):
        OpenHarnessIntegration._instance = None
        integration = OpenHarnessIntegration()
        status = integration.get_status()
        assert "openharness_available" in status
        assert status["agent_loop_initialized"] is False
        assert status["llm_client_initialized"] is False
        assert status["tools_count"] == 0
        OpenHarnessIntegration._instance = None
