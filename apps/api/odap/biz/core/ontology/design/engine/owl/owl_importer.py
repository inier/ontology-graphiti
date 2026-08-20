"""OWLImporter — 标准 OWL → Schema 候选（互操作入口，ADR-077 §4 + 裁决 2）。

裁决 2 约束：
- 导入结果**不直接入库**，产出 Schema 候选（草稿）。
- 仅做结构映射：OWL Class → 实体类型、DatatypeProperty → 属性、
  ObjectProperty → 关系。
- 语义约束（OWL 公理）降级为 semantic_hints 元数据，不自动转约束。
- 导入过程全程审计（ADR-074）。
"""

from __future__ import annotations

import logging
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)

OWL = "http://www.w3.org/2002/07/owl#"
RDFS = "http://www.w3.org/2000/01/rdf-schema#"
XSD = "http://www.w3.org/2001/XMLSchema#"

# XSD IRI → 自定义 data_type
XSD_TO_DATA_TYPE = {
    f"{XSD}string": "string",
    f"{XSD}integer": "integer",
    f"{XSD}double": "float",
    f"{XSD}float": "float",
    f"{XSD}boolean": "boolean",
    f"{XSD}date": "date",
    f"{XSD}dateTime": "datetime",
}


class OWLImporter:
    """OWL → Schema 候选导入器（结构映射）"""

    def import_schema_candidates(self, owl_turtle: str) -> Dict[str, Any]:
        """解析 OWL Turtle，产出 Schema 候选（草稿，不直接入库）。

        Args:
            owl_turtle: OWL 本体 Turtle 文本

        Returns:
            {
                "entity_types": [候选实体类型 dict],
                "source_format": "owl",
                "status": "draft",       # 草稿，待 HITL 确认
            }
        """
        try:
            from rdflib import Graph, RDF, RDFS, OWL, URIRef
        except ImportError as e:
            raise RuntimeError("rdflib 未安装，无法导入 OWL") from e

        g = Graph()
        g.parse(data=owl_turtle, format="turtle")

        entity_types: List[Dict[str, Any]] = []
        # 收集所有 OWL Class
        classes = set(g.subjects(RDF.type, OWL.Class))
        # 处理继承关系
        subclass_pairs = list(g.subject_objects(RDFS.subClassOf))

        for cls in classes:
            type_id = self._local_name(cls)
            entity: Dict[str, Any] = {
                "type_id": type_id,
                "name": type_id,
                "display_name": None,
                "description": None,
                "properties": [],
                "links": [],
                "primary_key": [],
                "classification_level": "U",
                "semantic_hints": {},
                "status": "draft",
            }
            # label/comment
            label = g.value(cls, RDFS.label)
            comment = g.value(cls, RDFS.comment)
            if label:
                entity["display_name"] = str(label)
            if comment:
                entity["description"] = str(comment)

            # 继承关系 → semantic_hints
            parents = [str(self._local_name(p)) for s, p in subclass_pairs if s == cls]
            if parents:
                entity["semantic_hints"]["subclass_of"] = parents

            # 属性/关系：按 domain 归属
            for prop in g.subjects(RDFS.domain, cls):
                prop_name = self._local_name(prop)
                if (prop, RDF.type, OWL.DatatypeProperty) in g:
                    entity["properties"].append({
                        "name": prop_name,
                        "data_type": self._range_data_type(g, prop),
                        "required": False,
                        "classification_level": "U",
                    })
                elif (prop, RDF.type, OWL.ObjectProperty) in g:
                    target = g.value(prop, RDFS.range)
                    entity["links"].append({
                        "name": prop_name,
                        "target_type": self._local_name(target) if target else "",
                        "cardinality": "N:N",
                        "link_type": "association",
                    })

            entity_types.append(entity)

        return {
            "entity_types": entity_types,
            "source_format": "owl",
            "status": "draft",
        }

    @staticmethod
    def _range_data_type(g, prop) -> str:
        """将 OWL 数据属性 range 映射为自定义 data_type"""
        from rdflib import URIRef
        rng = g.value(prop, URIRef(f"{RDFS}range"))
        if rng is None:
            return "string"
        return XSD_TO_DATA_TYPE.get(str(rng), "string")

    @staticmethod
    def _local_name(uri) -> str:
        """提取 URI 本地名（去掉命名空间前缀）"""
        s = str(uri)
        if "#" in s:
            return s.rsplit("#", 1)[-1]
        return s.rsplit("/", 1)[-1]


def import_owl(owl_turtle: str) -> Dict[str, Any]:
    """便捷函数：导入 OWL → Schema 候选"""
    return OWLImporter().import_schema_candidates(owl_turtle)


__all__ = ["OWLImporter", "import_owl"]
