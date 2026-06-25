import sys
import pytest
from unittest.mock import patch, MagicMock


@pytest.fixture
def template_gen():
    from odap.biz.core.ontology.extraction.impl.template_generator import TemplateGenerator
    return TemplateGenerator()


_DEFAULT_OBJECT_TYPES = [
    {
        "name": "Company",
        "properties": [
            {"name": "name", "property_type": "STRING"},
            {"name": "revenue", "property_type": "FLOAT"},
        ],
    },
    {
        "name": "Person",
        "properties": [
            {"name": "full_name", "property_type": "STRING"},
        ],
    },
]

_DEFAULT_LINK_TYPES = [
    {
        "name": "employs",
        "source_type": "Company",
        "target_type": "Person",
        "link_type": "ASSOCIATION",
    },
]


def _make_ontology_result(object_types=_DEFAULT_OBJECT_TYPES, link_types=_DEFAULT_LINK_TYPES):
    return {
        "name": "test-ontology",
        "object_types": object_types,
        "link_types": link_types,
    }


def _patch_ontology_service(svc):
    return patch(
        "odap.biz.core.ontology.ontology_api.services.ontology_service.OntologyService",
        return_value=svc,
    )


def _patch_news_ingester(ingester):
    mock_module = MagicMock()
    mock_module.NewsIngester = MagicMock(return_value=ingester)
    return patch.dict(sys.modules, {
        "odap.biz.data.knowledge_base.ingestion": mock_module,
        "odap.biz.data.knowledge_base.ingestion.news_ingester": mock_module,
    })


class TestTemplateGenerator:

    def test_generate_from_ontology_success(self, template_gen):
        svc = MagicMock()
        svc.get_ontology.return_value = _make_ontology_result()
        with _patch_ontology_service(svc):
            result = template_gen.generate_from_ontology("abc12345-6789")
        assert result is not None
        assert result["auto_type"] == "graph"
        assert result["method"] == "graph_rag"
        assert result["language"] == "zh"
        assert result["source"] == "generated_from_ontology"
        assert "node_schema" in result
        assert "Company" in result["node_schema"]
        assert "Person" in result["node_schema"]
        assert result["node_schema"]["Company"]["name"]["type"] == "string"
        assert result["node_schema"]["Company"]["revenue"]["type"] == "float"
        assert "edge_schema" in result
        assert "employs" in result["edge_schema"]
        assert result["edge_schema"]["employs"]["source"] == "Company"
        assert result["edge_schema"]["employs"]["target"] == "Person"
        assert result["name"].startswith("ontology_abc12345")

    def test_generate_from_ontology_empty_types(self, template_gen):
        svc = MagicMock()
        svc.get_ontology.return_value = _make_ontology_result(object_types=[], link_types=[])
        with _patch_ontology_service(svc):
            result = template_gen.generate_from_ontology("ont-1")
        assert result is None

    def test_generate_from_ontology_service_error(self, template_gen):
        svc = MagicMock()
        svc.get_ontology.return_value = {"status": "error", "message": "not found"}
        with _patch_ontology_service(svc):
            result = template_gen.generate_from_ontology("ont-1")
        assert result is None

    def test_generate_from_ontology_exception(self, template_gen):
        svc = MagicMock()
        svc.get_ontology.side_effect = RuntimeError("db down")
        with _patch_ontology_service(svc):
            result = template_gen.generate_from_ontology("ont-1")
        assert result is None

    def test_select_preset_finance(self, template_gen):
        result = template_gen.select_preset("finance")
        assert result is not None
        assert result["name"] == "finance/earnings_summary"
        assert result["auto_type"] == "graph"
        assert result["source"] == "preset"

    def test_select_preset_legal(self, template_gen):
        result = template_gen.select_preset("legal")
        assert result is not None
        assert result["name"] == "legal/contract_obligation"
        assert result["source"] == "preset"

    def test_select_preset_unknown(self, template_gen):
        result = template_gen.select_preset("astronomy")
        assert result is not None
        assert result["name"] == "general/base_graph"
        assert result["source"] == "preset"

    def test_generate_with_web_search_success(self, template_gen):
        ingester = MagicMock()
        ingester.search.return_value = [{"title": "金融新闻", "content": "股票上涨"}]
        with _patch_news_ingester(ingester):
            result = template_gen.generate_with_web_search("金融投资分析")
        assert result is not None
        assert result["source"] == "preset"
        assert result["name"] == "finance/earnings_summary"
        ingester.search.assert_called_once_with("金融投资分析", max_results=5)

    def test_generate_with_web_search_failure(self, template_gen):
        ingester = MagicMock()
        ingester.search.side_effect = ConnectionError("network unreachable")
        with _patch_news_ingester(ingester):
            result = template_gen.generate_with_web_search("some text")
        assert result is not None
        assert result["name"] == "general/base_graph"
        assert result["source"] == "preset"

    def test_recommend_templates_returns_top_k(self, template_gen):
        result = template_gen.recommend_templates("generic text", top_k=2)
        assert len(result) == 2
        for item in result:
            assert "name" in item
            assert "score" in item

    def test_recommend_templates_domain_boost(self, template_gen):
        result = template_gen.recommend_templates("finance 投资分析", top_k=5)
        finance_items = [r for r in result if r["domain"] == "finance"]
        general_items = [r for r in result if r["domain"] == "general" and r["name"] == "general/base_graph"]
        assert len(finance_items) > 0
        assert finance_items[0]["score"] > general_items[0]["score"]

    def test_recommend_templates_default_order(self, template_gen):
        result = template_gen.recommend_templates("完全无关的文本", top_k=5)
        scores = [r["score"] for r in result]
        assert scores == sorted(scores, reverse=True)

    def test_infer_domain_finance(self, template_gen):
        assert template_gen._infer_domain("金融市场分析") == "finance"
        assert template_gen._infer_domain("股票投资策略") == "finance"
        assert template_gen._infer_domain("finance report") == "finance"

    def test_infer_domain_general(self, template_gen):
        assert template_gen._infer_domain("今天天气不错") == "general"
        assert template_gen._infer_domain("random text without keywords") == "general"
