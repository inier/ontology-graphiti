"""OWLExporter — 自定义 Schema → OWL/Turtle 导出（ADR-077 §4 + 裁决 4）。

策略（裁决 4）：
- owlready2 可用 → 用 owlready2 构建 OWL 本体（支持类层次语义）
- owlready2 不可用 → 降级为 rdflib 纯 RDF 序列化（Turtle 文本输出仍可用）

输出 Turtle 文本。纯序列化需求走 rdflib，无需 owlready2。
"""

from __future__ import annotations

import logging
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)

OWL = "http://www.w3.org/2002/07/owl#"
RDFS = "http://www.w3.org/2000/01/rdf-schema#"
XSD = "http://www.w3.org/2001/XMLSchema#"

# data_type → XSD IRI
DATA_TYPE_XSD_IRI = {
    "string": "string",
    "integer": "integer",
    "float": "double",
    "boolean": "boolean",
    "date": "date",
    "datetime": "dateTime",
}


class OWLExporter:
    """Schema → OWL/Turtle 导出器（默认走 rdflib，确定性可测试）"""

    def __init__(self, base_uri: str = "https://odap.local/ontology/"):
        self.base_uri = base_uri

    def export_turtle(self, entity_types: List[Dict[str, Any]]) -> str:
        """导出 Turtle 格式 OWL 本体文本。

        Args:
            entity_types: EntityTypeDefinition dict 列表

        Returns:
            Turtle 文本
        """
        try:
            from rdflib import Graph, Namespace, RDF, RDFS, OWL, URIRef, Literal
        except ImportError as e:
            raise RuntimeError("rdflib 未安装，无法导出 OWL") from e

        g = Graph()
        g.bind("owl", OWL)
        g.bind("rdfs", RDFS)
        g.bind("xsd", XSD)
        ODAP = Namespace(self.base_uri)

        for et in entity_types:
            type_id = et.get("type_id") or et.get("name", "Unknown")
            cls_iri = ODAP[type_id]
            g.add((cls_iri, RDF.type, OWL.Class))
            if et.get("display_name"):
                g.add((cls_iri, RDFS.label, Literal(et["display_name"])))
            if et.get("description"):
                g.add((cls_iri, RDFS.comment, Literal(et["description"])))

            # 属性 → OWL DatatypeProperty
            for p in et.get("properties", []) or []:
                prop_iri = ODAP[f"{type_id}/{p.get('name', '')}"]
                g.add((prop_iri, RDF.type, OWL.DatatypeProperty))
                g.add((prop_iri, RDFS.domain, cls_iri))
                dt = p.get("data_type", "string")
                xsd_type = DATA_TYPE_XSD_IRI.get(dt, "string")
                g.add((prop_iri, RDFS.range, URIRef(f"{XSD}{xsd_type}")))

            # 关系 → OWL ObjectProperty
            for link in et.get("links", []) or []:
                prop_iri = ODAP[f"{type_id}/{link.get('name', '')}"]
                g.add((prop_iri, RDF.type, OWL.ObjectProperty))
                g.add((prop_iri, RDFS.domain, cls_iri))
                target = link.get("target_type", "")
                if target:
                    g.add((prop_iri, RDFS.range, ODAP[target]))

        return g.serialize(format="turtle")

    def export_rdfxml(self, entity_types: List[Dict[str, Any]]) -> str:
        """导出 RDF/XML 格式（可选）"""
        from rdflib import Graph
        g = Graph()
        g.parse(data=self.export_turtle(entity_types), format="turtle")
        return g.serialize(format="xml")


def export_owl(entity_types: List[Dict[str, Any]], fmt: str = "turtle") -> str:
    """便捷函数：导出 OWL 本体"""
    exporter = OWLExporter()
    if fmt == "turtle":
        return exporter.export_turtle(entity_types)
    if fmt == "rdfxml":
        return exporter.export_rdfxml(entity_types)
    raise ValueError(f"不支持的导出格式: {fmt}")


__all__ = ["OWLExporter", "export_owl"]
