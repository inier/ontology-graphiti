"""Unit tests for HEAdapter (data.hyper_extract.impl.he_adapter).

Tests verify correct HE API usage:
- Template.create(source=, language=, llm_client=, embedder=)
- BaseAutoType.feed_text() (not evolve)
- .nodes/.edges access (not dump_dict)
- merge_results dedup by entity name + relation triplet
- trial_extract returns metrics dict
- RuntimeError when HE unavailable (no silent fallback)
"""

import sys
import types

import pytest
from unittest.mock import MagicMock, patch, call


def _install_fake_hyperextract():
    """Inject a fake hyperextract package + hyperextract.utils.client into sys.modules.

    The adapter __init__ does `from hyperextract import Template, AutoGraph`
    and `from hyperextract.utils.client import create_llm, create_embedder`.
    We synthesize a minimal package hierarchy so the imports succeed.
    """
    he_pkg = types.ModuleType("hyperextract")
    he_pkg.Template = MagicMock()
    he_pkg.AutoGraph = MagicMock()

    utils_pkg = types.ModuleType("hyperextract.utils")
    client_pkg = types.ModuleType("hyperextract.utils.client")
    client_pkg.create_llm = MagicMock()
    client_pkg.create_embedder = MagicMock()
    utils_pkg.client = client_pkg
    he_pkg.utils = utils_pkg

    return {
        "hyperextract": he_pkg,
        "hyperextract.utils": utils_pkg,
        "hyperextract.utils.client": client_pkg,
    }


class TestHEAdapterAvailability:
    @pytest.fixture
    def he_adapter_cls(self):
        from odap.biz.data.hyper_extract.impl.he_adapter import HEAdapter
        return HEAdapter

    def test_is_available_returns_true_when_he_imported(self, he_adapter_cls):
        fake_modules = _install_fake_hyperextract()
        with patch.dict(sys.modules, fake_modules, clear=False):
            adapter = he_adapter_cls()
            assert adapter.is_available() is True

    def test_is_available_returns_false_when_he_not_imported(self, he_adapter_cls):
        # Force ImportError by setting hyperextract to None in sys.modules
        with patch.dict(sys.modules, {"hyperextract": None, "hyperextract.utils": None, "hyperextract.utils.client": None}):
            adapter = he_adapter_cls()
            assert adapter.is_available() is False


class TestHEAdapterParse:
    @pytest.fixture
    def adapter(self):
        """Create an HEAdapter with mocked HE internals."""
        from odap.biz.data.hyper_extract.impl.he_adapter import HEAdapter
        with patch.object(HEAdapter, "__init__", lambda self: None):
            adapter = HEAdapter()
            adapter._available = True
            adapter._Template = MagicMock()
            adapter._AutoGraph = MagicMock()
            adapter._create_llm_fn = MagicMock(return_value=MagicMock())
            adapter._create_embedder_fn = MagicMock(return_value=MagicMock())
        return adapter

    def test_parse_calls_template_create_with_correct_kwargs(self, adapter):
        """Verify Template.create uses llm_client= and embedder= (not llm=/emb=)."""
        mock_ka = MagicMock()
        mock_ka.nodes = [MagicMock(name="A", type="person", description="test")]
        mock_ka.edges = []
        mock_template = MagicMock()
        mock_template.parse.return_value = mock_ka
        adapter._Template.create.return_value = mock_template

        adapter.parse("some text", template={"template_path": "general/graph"})

        adapter._Template.create.assert_called_once()
        _, kwargs = adapter._Template.create.call_args
        assert "llm_client" in kwargs, "Must use llm_client= kwarg"
        assert "embedder" in kwargs, "Must use embedder= kwarg"
        assert "llm" not in kwargs, "Must NOT use llm= kwarg"
        assert "emb" not in kwargs, "Must NOT use emb= kwarg"

    def test_parse_calls_template_parse_with_text(self, adapter):
        mock_ka = MagicMock()
        mock_ka.nodes = []
        mock_ka.edges = []
        mock_template = MagicMock()
        mock_template.parse.return_value = mock_ka
        adapter._Template.create.return_value = mock_template

        adapter.parse("test text", template={"template_path": "general/graph"})

        mock_template.parse.assert_called_once_with("test text")

    def test_parse_returns_normalized_result(self, adapter):
        mock_node = MagicMock()
        mock_node.name = "Customer"
        mock_node.type = "object"
        mock_node.description = "A customer"
        mock_node.properties = {"id": "string"}

        mock_edge = MagicMock()
        mock_edge.source = "Customer"
        mock_edge.target = "Order"
        mock_edge.relation_type = "places"
        mock_edge.properties = {}

        mock_ka = MagicMock()
        mock_ka.nodes = [mock_node]
        mock_ka.edges = [mock_edge]
        mock_template = MagicMock()
        mock_template.parse.return_value = mock_ka
        adapter._Template.create.return_value = mock_template

        result = adapter.parse("text", template={"template_path": "general/graph"})

        assert "entities" in result
        assert "relations" in result
        assert len(result["entities"]) == 1
        assert result["entities"][0]["name"] == "Customer"
        assert len(result["relations"]) == 1
        assert result["relations"][0]["source"] == "Customer"

    def test_parse_returns_none_for_empty_text(self, adapter):
        result = adapter.parse("")
        assert result is None

    def test_parse_raises_runtime_error_when_unavailable(self, adapter):
        adapter._available = False
        with pytest.raises(RuntimeError, match="hyperextract"):
            adapter.parse("text", template={"template_path": "general/graph"})


class TestHEAdapterParseBatch:
    @pytest.fixture
    def adapter(self):
        from odap.biz.data.hyper_extract.impl.he_adapter import HEAdapter
        with patch.object(HEAdapter, "__init__", lambda self: None):
            adapter = HEAdapter()
            adapter._available = True
            adapter._Template = MagicMock()
            adapter._AutoGraph = MagicMock()
            adapter._create_llm_fn = MagicMock(return_value=MagicMock())
            adapter._create_embedder_fn = MagicMock(return_value=MagicMock())
        return adapter

    def test_parse_batch_returns_list_of_results(self, adapter):
        mock_ka = MagicMock()
        mock_ka.nodes = []
        mock_ka.edges = []
        mock_template = MagicMock()
        mock_template.parse.return_value = mock_ka
        adapter._Template.create.return_value = mock_template

        results = adapter.parse_batch(["text1", "text2"], template={"template_path": "g"})

        assert isinstance(results, list)
        assert len(results) == 2

    def test_parse_batch_isolates_per_text_errors(self, adapter):
        mock_ka = MagicMock()
        mock_ka.nodes = []
        mock_ka.edges = []
        mock_template = MagicMock()
        mock_template.parse.side_effect = [mock_ka, Exception("LLM error"), mock_ka]
        adapter._Template.create.return_value = mock_template

        results = adapter.parse_batch(["t1", "t2", "t3"], template={"template_path": "g"})

        assert len(results) == 3
        assert results[0] is not None
        assert results[1] is None  # failed text returns None
        assert results[2] is not None


class TestHEAdapterFeedText:
    @pytest.fixture
    def adapter(self):
        from odap.biz.data.hyper_extract.impl.he_adapter import HEAdapter
        with patch.object(HEAdapter, "__init__", lambda self: None):
            adapter = HEAdapter()
            adapter._available = True
        return adapter

    def test_feed_text_calls_feed_text_not_evolve(self, adapter):
        """Verify feed_text() calls BaseAutoType.feed_text() (not evolve)."""
        mock_ka = MagicMock()
        mock_ka.nodes = []
        mock_ka.edges = []
        mock_ka.feed_text.return_value = mock_ka

        result = adapter.feed_text(mock_ka, "new text")

        mock_ka.feed_text.assert_called_once_with("new text")
        mock_ka.evolve.assert_not_called() if hasattr(mock_ka, 'evolve') else None

    def test_feed_text_returns_normalized_result(self, adapter):
        mock_node = MagicMock()
        mock_node.name = "Entity1"
        mock_node.type = "concept"
        mock_node.description = ""
        mock_node.properties = {}

        mock_ka = MagicMock()
        mock_ka.nodes = [mock_node]
        mock_ka.edges = []
        mock_ka.feed_text.return_value = mock_ka

        result = adapter.feed_text(mock_ka, "new text")

        assert "entities" in result
        assert len(result["entities"]) == 1

    def test_feed_text_raises_runtime_error_when_unavailable(self, adapter):
        adapter._available = False
        with pytest.raises(RuntimeError, match="hyperextract"):
            adapter.feed_text(MagicMock(), "text")

    def test_feed_text_returns_none_for_empty_text(self, adapter):
        result = adapter.feed_text(MagicMock(), "")
        assert result is None


class TestHEAdapterMergeResults:
    @pytest.fixture
    def adapter(self):
        from odap.biz.data.hyper_extract.impl.he_adapter import HEAdapter
        with patch.object(HEAdapter, "__init__", lambda self: None):
            adapter = HEAdapter()
            adapter._available = True
        return adapter

    def test_merge_results_empty_list(self, adapter):
        result = adapter.merge_results([])
        assert result == {"entities": [], "relations": []}

    def test_merge_results_single_item(self, adapter):
        single = {"entities": [{"name": "A"}], "relations": []}
        result = adapter.merge_results([single])
        assert len(result["entities"]) == 1

    def test_merge_results_deduplicates_entities_by_name(self, adapter):
        data1 = {"entities": [{"name": "A", "type": "person"}, {"name": "B", "type": "org"}], "relations": []}
        data2 = {"entities": [{"name": "A", "type": "person-dup"}, {"name": "C", "type": "concept"}], "relations": []}
        result = adapter.merge_results([data1, data2])
        names = [e["name"] for e in result["entities"]]
        assert names == ["A", "B", "C"]
        # Keep first occurrence
        assert result["entities"][0]["type"] == "person"

    def test_merge_results_deduplicates_relations_by_triplet(self, adapter):
        data1 = {
            "entities": [{"name": "A"}, {"name": "B"}],
            "relations": [{"source": "A", "target": "B", "relation_type": "creates"}],
        }
        data2 = {
            "entities": [{"name": "C"}],
            "relations": [
                {"source": "A", "target": "B", "relation_type": "creates"},  # dup
                {"source": "A", "target": "C", "relation_type": "uses"},
            ],
        }
        result = adapter.merge_results([data1, data2])
        assert len(result["relations"]) == 2

    def test_merge_results_merges_multiple(self, adapter):
        data1 = {"entities": [{"name": "A"}, {"name": "B"}], "relations": [{"source": "A", "target": "B", "relation_type": "r1"}]}
        data2 = {"entities": [{"name": "C"}], "relations": [{"source": "B", "target": "C", "relation_type": "r2"}]}
        data3 = {"entities": [{"name": "D"}], "relations": [{"source": "C", "target": "D", "relation_type": "r3"}]}
        result = adapter.merge_results([data1, data2, data3])
        assert len(result["entities"]) == 4
        assert len(result["relations"]) == 3

    def test_merge_results_handles_missing_keys(self, adapter):
        data1 = {"entities": [{"name": "A"}]}
        data2 = {"relations": [{"source": "A", "target": "B", "relation_type": "r"}]}
        data3 = {}
        result = adapter.merge_results([data1, data2, data3])
        assert len(result["entities"]) == 1
        assert len(result["relations"]) == 1


class TestHEAdapterTrialExtract:
    @pytest.fixture
    def adapter(self):
        from odap.biz.data.hyper_extract.impl.he_adapter import HEAdapter
        with patch.object(HEAdapter, "__init__", lambda self: None):
            adapter = HEAdapter()
            adapter._available = True
            adapter._Template = MagicMock()
            adapter._AutoGraph = MagicMock()
            adapter._create_llm_fn = MagicMock(return_value=MagicMock())
            adapter._create_embedder_fn = MagicMock(return_value=MagicMock())
        return adapter

    def test_trial_extract_truncates_text(self, adapter):
        long_text = "A" * 3000
        mock_ka = MagicMock()
        mock_ka.nodes = [MagicMock(name="E1", type="t1", description="", properties={})]
        mock_ka.edges = []
        mock_template = MagicMock()
        mock_template.parse.return_value = mock_ka
        adapter._Template.create.return_value = mock_template

        adapter.trial_extract(long_text, template={"template_path": "g"}, sample_size=1500)

        # Verify parse was called with truncated text (positional first arg)
        args, _ = mock_template.parse.call_args
        assert len(args[0]) == 1500

    def test_trial_extract_returns_metrics(self, adapter):
        mock_node1 = MagicMock()
        mock_node1.name = "E1"
        mock_node1.type = "person"
        mock_node1.description = "desc"
        mock_node1.properties = {"id": "string"}

        mock_node2 = MagicMock()
        mock_node2.name = "E2"
        mock_node2.type = "org"
        mock_node2.description = ""
        mock_node2.properties = {}

        mock_edge = MagicMock()
        mock_edge.source = "E1"
        mock_edge.target = "E2"
        mock_edge.relation_type = "works_for"
        mock_edge.properties = {}

        mock_ka = MagicMock()
        mock_ka.nodes = [mock_node1, mock_node2]
        mock_ka.edges = [mock_edge]
        mock_template = MagicMock()
        mock_template.parse.return_value = mock_ka
        adapter._Template.create.return_value = mock_template

        result = adapter.trial_extract("test text", template={"template_path": "g"})

        assert "entity_count" in result
        assert "relation_count" in result
        assert "field_coverage" in result
        assert "type_diversity" in result
        assert "types_found" in result
        assert result["entity_count"] == 2
        assert result["relation_count"] == 1
        assert sorted(result["types_found"]) == ["org", "person"]

    def test_trial_extract_default_sample_size_1500(self, adapter):
        long_text = "X" * 5000
        mock_ka = MagicMock()
        mock_ka.nodes = []
        mock_ka.edges = []
        mock_template = MagicMock()
        mock_template.parse.return_value = mock_ka
        adapter._Template.create.return_value = mock_template

        adapter.trial_extract(long_text, template={"template_path": "g"})

        # Default sample_size=1500 should truncate to 1500 chars
        args, _ = mock_template.parse.call_args
        assert len(args[0]) == 1500

    def test_trial_extract_raises_runtime_error_when_unavailable(self, adapter):
        adapter._available = False
        with pytest.raises(RuntimeError, match="hyperextract"):
            adapter.trial_extract("text", template={"template_path": "g"})
