import logging
import os
from typing import Any, Dict, List, Optional

from odap.biz.core.ontology.extraction.interfaces.extraction_interfaces import TemplateGeneratorInterface

logger = logging.getLogger(__name__)

_HE_AVAILABLE = False
try:
    from hyperextract.utils.template_engine.gallery import Gallery
    _HE_AVAILABLE = True
except ImportError:
    pass


class TemplateGenerator(TemplateGeneratorInterface):
    def __init__(self):
        self._available = _HE_AVAILABLE

    def generate_from_ontology(self, ontology_id: str) -> Optional[Dict[str, Any]]:
        try:
            from odap.biz.core.ontology.ontology_api.services.ontology_service import OntologyService
            svc = OntologyService()
            result = svc.get_ontology(ontology_id)
            if not result or result.get("status") == "error":
                return None
            object_types = result.get("object_types", [])
            if not object_types:
                return None
            node_schema = {}
            for ot in object_types:
                name = ot.get("name", "")
                props = {}
                for p in ot.get("properties", []):
                    props[p.get("name", "")] = {"type": p.get("property_type", "STRING").lower()}
                node_schema[name] = props
            edge_schema = {}
            for lt in result.get("link_types", []):
                edge_schema[lt.get("name", "")] = {
                    "source": lt.get("source_type", ""),
                    "target": lt.get("target_type", ""),
                    "type": lt.get("link_type", "ASSOCIATION"),
                }
            return {
                "name": f"ontology_{ontology_id[:8]}",
                "auto_type": "graph",
                "method": "graph_rag",
                "language": "zh",
                "node_schema": node_schema,
                "edge_schema": edge_schema,
                "source": "generated_from_ontology",
            }
        except Exception as e:
            logger.warning(f"Failed to generate template from ontology: {e}")
            return None

    def select_preset(self, domain_hint: str) -> Optional[Dict[str, Any]]:
        domain_map = {
            "finance": "finance/earnings_summary",
            "legal": "legal/contract_obligation",
            "medicine": "medicine/treatment_map",
            "tcm": "tcm/herb_property",
            "industry": "industry/equipment_topology",
        }
        template_name = domain_map.get(domain_hint, "general/base_graph")
        return {
            "name": template_name,
            "auto_type": "graph",
            "method": "graph_rag",
            "language": "zh",
            "source": "preset",
        }

    def generate_with_web_search(self, text: str) -> Optional[Dict[str, Any]]:
        try:
            from odap.biz.data.knowledge_base.ingestion.news_ingester import NewsIngester
            ingester = NewsIngester()
            search_results = ingester.search(text, max_results=5)
            domain = self._infer_domain(text, search_results)
            return self.select_preset(domain)
        except Exception as e:
            logger.warning(f"Web search template generation failed: {e}")
            return self.select_preset("general")

    def recommend_templates(self, text: str, top_k: int = 3) -> List[Dict[str, Any]]:
        presets = [
            {"name": "general/base_graph", "description": "通用知识图谱", "domain": "general", "score": 0.5},
            {"name": "general/concept_graph", "description": "概念关系图", "domain": "general", "score": 0.4},
            {"name": "general/biography_graph", "description": "人物关系图", "domain": "general", "score": 0.3},
            {"name": "finance/ownership_graph", "description": "股权关系图", "domain": "finance", "score": 0.3},
            {"name": "legal/defined_term_set", "description": "法律术语集", "domain": "legal", "score": 0.3},
        ]
        for p in presets:
            domain = p["domain"]
            if domain in text.lower():
                p["score"] += 0.3
        presets.sort(key=lambda x: x["score"], reverse=True)
        return presets[:top_k]

    def _infer_domain(self, text: str, search_results: Any = None) -> str:
        keywords = {
            "finance": ["金融", "股票", "投资", "finance", "stock", "investment"],
            "legal": ["法律", "合同", "法规", "legal", "contract", "law"],
            "medicine": ["医疗", "药物", "诊断", "medicine", "drug", "diagnosis"],
            "tcm": ["中医", "中药", "经络", "herb", "meridian"],
            "industry": ["工业", "设备", "安全", "industry", "equipment", "safety"],
        }
        text_lower = text.lower()
        for domain, kws in keywords.items():
            if any(kw in text_lower for kw in kws):
                return domain
        return "general"

    def list_all_presets(self) -> List[Dict[str, Any]]:
        return [
            {"name": "general/base_graph", "description": "通用知识图谱", "domain": "general", "source": "preset"},
            {"name": "general/concept_graph", "description": "概念关系图", "domain": "general", "source": "preset"},
            {"name": "general/biography_graph", "description": "人物关系图", "domain": "general", "source": "preset"},
            {"name": "finance/earnings_summary", "description": "财报摘要", "domain": "finance", "source": "preset"},
            {"name": "finance/ownership_graph", "description": "股权关系图", "domain": "finance", "source": "preset"},
            {"name": "legal/contract_obligation", "description": "合同义务", "domain": "legal", "source": "preset"},
            {"name": "legal/defined_term_set", "description": "法律术语集", "domain": "legal", "source": "preset"},
            {"name": "medicine/treatment_map", "description": "诊疗图谱", "domain": "medicine", "source": "preset"},
            {"name": "tcm/herb_property", "description": "中药属性", "domain": "tcm", "source": "preset"},
            {"name": "industry/equipment_topology", "description": "设备拓扑", "domain": "industry", "source": "preset"},
        ]
