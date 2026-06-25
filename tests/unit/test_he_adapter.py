import logging
import sys
from unittest.mock import MagicMock, patch

import pytest


class TestHEAdapter:
    @pytest.fixture
    def he_adapter_cls(self):
        from odap.biz.core.ontology.extraction.impl.he_adapter import HEAdapter
        return HEAdapter

    @pytest.fixture
    def he_module(self):
        import odap.biz.core.ontology.extraction.impl.he_adapter as mod
        return mod

    def _make_adapter(self, he_adapter_cls, available=True):
        with patch.object(he_adapter_cls, "__init__", lambda self: None):
            adapter = he_adapter_cls()
            adapter._available = available
        return adapter

    def test_available_property_true_when_he_importable(self, he_adapter_cls):
        adapter = self._make_adapter(he_adapter_cls, available=True)
        assert adapter.available is True

    def test_available_property_false_when_he_not_importable(self, he_adapter_cls):
        adapter = self._make_adapter(he_adapter_cls, available=False)
        assert adapter.available is False

    def test_extract_from_text_success(self, he_adapter_cls, he_module):
        ka = MagicMock()
        ka.dump_dict.return_value = {
            "nodes": [{"id": "n1", "label": "Person"}],
            "edges": [{"id": "e1", "source": "n1", "target": "n2"}],
        }
        template = MagicMock()
        template.parse.return_value = ka
        mock_template_cls = MagicMock()
        mock_template_cls.create.return_value = template

        adapter = self._make_adapter(he_adapter_cls, available=True)

        original = getattr(he_module, "Template", None)
        he_module.Template = mock_template_cls
        try:
            result = adapter.extract_from_text("some text", {"name": "test/tmpl"})
        finally:
            if original is not None:
                he_module.Template = original
            else:
                delattr(he_module, "Template")

        mock_template_cls.create.assert_called_once_with(
            "test/tmpl", "zh", llm=None, emb=None
        )
        template.parse.assert_called_once_with("some text")
        ka.dump_dict.assert_called_once()
        assert result == {
            "nodes": [{"id": "n1", "label": "Person"}],
            "edges": [{"id": "e1", "source": "n1", "target": "n2"}],
        }

    def test_extract_from_text_he_unavailable_raises(self, he_adapter_cls):
        adapter = self._make_adapter(he_adapter_cls, available=False)
        with pytest.raises(RuntimeError, match="Hyper-Extract is not available"):
            adapter.extract_from_text("text", {})

    def test_extract_from_text_with_custom_template_config(self, he_adapter_cls, he_module):
        ka = MagicMock()
        ka.dump_dict.return_value = {"nodes": [], "edges": []}
        template = MagicMock()
        template.parse.return_value = ka
        mock_template_cls = MagicMock()
        mock_template_cls.create.return_value = template

        mock_llm = MagicMock()
        mock_emb = MagicMock()
        config = {
            "name": "custom/graph_v2",
            "language": "en",
            "llm": mock_llm,
            "emb": mock_emb,
        }

        adapter = self._make_adapter(he_adapter_cls, available=True)

        original = getattr(he_module, "Template", None)
        he_module.Template = mock_template_cls
        try:
            adapter.extract_from_text("hello", config)
        finally:
            if original is not None:
                he_module.Template = original
            else:
                delattr(he_module, "Template")

        mock_template_cls.create.assert_called_once_with(
            "custom/graph_v2", "en", llm=mock_llm, emb=mock_emb
        )

    def test_extract_incremental_he_unavailable_raises(self, he_adapter_cls):
        adapter = self._make_adapter(he_adapter_cls, available=False)
        with pytest.raises(RuntimeError, match="Hyper-Extract is not available"):
            adapter.extract_incremental("/path/to/ka", "text")

    def test_extract_incremental_logs_info(self, he_adapter_cls, caplog):
        adapter = self._make_adapter(he_adapter_cls, available=True)

        with caplog.at_level(logging.INFO, logger="odap.biz.core.ontology.extraction.impl.he_adapter"):
            result = adapter.extract_incremental("/data/ka.json", "more text")

        assert "Incremental extraction from ka_path=/data/ka.json" in caplog.text
        assert result == {"nodes": [], "edges": []}

    def test_merge_results_empty_list(self, he_adapter_cls):
        adapter = self._make_adapter(he_adapter_cls)
        result = adapter.merge_results([])
        assert result == {"nodes": [], "edges": []}

    def test_merge_results_single_item(self, he_adapter_cls):
        single = {"nodes": [{"id": "n1"}], "edges": [{"id": "e1"}]}
        adapter = self._make_adapter(he_adapter_cls)
        result = adapter.merge_results([single])
        assert result == single

    def test_merge_results_deduplicates_nodes_by_id(self, he_adapter_cls):
        data1 = {"nodes": [{"id": "n1", "label": "A"}, {"id": "n2", "label": "B"}], "edges": []}
        data2 = {"nodes": [{"id": "n1", "label": "A-dup"}, {"id": "n3", "label": "C"}], "edges": []}
        adapter = self._make_adapter(he_adapter_cls)
        result = adapter.merge_results([data1, data2])
        node_ids = [n["id"] for n in result["nodes"]]
        assert node_ids == ["n1", "n2", "n3"]
        assert result["nodes"][0]["label"] == "A"

    def test_merge_results_deduplicates_edges_by_id(self, he_adapter_cls):
        data1 = {"nodes": [], "edges": [{"id": "e1", "source": "a"}, {"id": "e2", "source": "b"}]}
        data2 = {"nodes": [], "edges": [{"id": "e1", "source": "a-dup"}, {"id": "e3", "source": "c"}]}
        adapter = self._make_adapter(he_adapter_cls)
        result = adapter.merge_results([data1, data2])
        edge_ids = [e["id"] for e in result["edges"]]
        assert edge_ids == ["e1", "e2", "e3"]
        assert result["edges"][0]["source"] == "a"

    def test_merge_results_merges_multiple_results(self, he_adapter_cls):
        data1 = {
            "nodes": [{"id": "n1"}, {"id": "n2"}],
            "edges": [{"id": "e1"}],
        }
        data2 = {
            "nodes": [{"id": "n3"}],
            "edges": [{"id": "e2"}, {"id": "e3"}],
        }
        data3 = {
            "nodes": [{"id": "n4"}],
            "edges": [{"id": "e4"}],
        }
        adapter = self._make_adapter(he_adapter_cls)
        result = adapter.merge_results([data1, data2, data3])
        assert len(result["nodes"]) == 4
        assert len(result["edges"]) == 4
        assert [n["id"] for n in result["nodes"]] == ["n1", "n2", "n3", "n4"]
        assert [e["id"] for e in result["edges"]] == ["e1", "e2", "e3", "e4"]

    def test_merge_results_handles_empty_nodes_edges(self, he_adapter_cls):
        data1 = {"nodes": [{"id": "n1"}]}
        data2 = {"edges": [{"id": "e1"}]}
        data3 = {}
        adapter = self._make_adapter(he_adapter_cls)
        result = adapter.merge_results([data1, data2, data3])
        assert len(result["nodes"]) == 1
        assert len(result["edges"]) == 1
        assert result["nodes"][0]["id"] == "n1"
        assert result["edges"][0]["id"] == "e1"
