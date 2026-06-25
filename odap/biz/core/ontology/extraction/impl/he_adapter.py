import logging
from typing import Any, Dict, List, Optional

from odap.biz.core.ontology.extraction.interfaces.extraction_interfaces import ExtractionAdapterInterface

logger = logging.getLogger(__name__)

_HE_AVAILABLE = False
try:
    from hyperextract.utils.template_engine.template import Template
    _HE_AVAILABLE = True
except ImportError:
    logger.warning("Hyper-Extract not available, falling back to SchemaLevelExtractor")


class HEAdapter(ExtractionAdapterInterface):
    def __init__(self):
        self._available = _HE_AVAILABLE

    @property
    def available(self) -> bool:
        return self._available

    def extract_from_text(self, text: str, template_config: Dict[str, Any]) -> Dict[str, Any]:
        if not self._available:
            raise RuntimeError("Hyper-Extract is not available")
        template = Template.create(
            template_config.get("name", "general/base_graph"),
            template_config.get("language", "zh"),
            llm=template_config.get("llm"),
            emb=template_config.get("emb"),
        )
        ka = template.parse(text)
        return ka.dump_dict() if hasattr(ka, "dump_dict") else {"nodes": [], "edges": []}

    def extract_incremental(self, ka_path: str, text: str) -> Dict[str, Any]:
        if not self._available:
            raise RuntimeError("Hyper-Extract is not available")
        logger.info(f"Incremental extraction from ka_path={ka_path}")
        return {"nodes": [], "edges": []}

    def merge_results(self, data_list: List[Dict[str, Any]]) -> Dict[str, Any]:
        if not data_list:
            return {"nodes": [], "edges": []}
        if len(data_list) == 1:
            return data_list[0]
        merged_nodes = []
        merged_edges = []
        seen_nodes = set()
        seen_edges = set()
        for data in data_list:
            for node in data.get("nodes", []):
                nid = node.get("id", "")
                if nid and nid not in seen_nodes:
                    seen_nodes.add(nid)
                    merged_nodes.append(node)
            for edge in data.get("edges", []):
                eid = edge.get("id", "")
                if eid and eid not in seen_edges:
                    seen_edges.add(eid)
                    merged_edges.append(edge)
        return {"nodes": merged_nodes, "edges": merged_edges}
