"""SHACLValidator — 实例数据合规校验（ADR-077 §3 + 裁决 3）。

校验输入为显式传入的实例数据（JSON），由本模块负责：
  实例 JSON → RDF 临时图（rdflib）→ 套用实时生成的 SHACL shape → pySHACL 校验。

不直接读 Neo4j（避免跨层耦合）。pySHACL 不可用时抛错（校验是硬需求，
不降级静默通过）。

返回结构化报告：
  {
    "conforms": bool,
    "results": [{"focus_node", "path", "message", "severity"}, ...],
    "shape_count": int,
    "instance_count": int,
  }
"""

from __future__ import annotations

import logging
from typing import Any, Dict, List, Optional

from .shape_generator import ShapeGenerator

logger = logging.getLogger(__name__)

RDF_TYPE = "http://www.w3.org/1999/02/22-rdf-syntax-ns#type"


class SHACLValidator:
    """SHACL 校验器（pySHACL + rdflib）"""

    def __init__(self, base_uri: str = "https://odap.local/ontology/"):
        self.base_uri = base_uri
        self._shape_gen = ShapeGenerator(base_uri=base_uri)

    def validate(
        self,
        entity_types: List[Dict[str, Any]],
        instances: List[Dict[str, Any]],
    ) -> Dict[str, Any]:
        """校验实例数据是否符合实体类型定义的 SHACL 约束。

        Args:
            entity_types: EntityTypeDefinition dict 列表（生成 shape）
            instances: 实例 dict 列表，每个含 type_id + properties

        Returns:
            结构化校验报告
        """
        try:
            from rdflib import Graph, Namespace, RDF, Literal, URIRef
        except ImportError as e:
            raise RuntimeError("rdflib 未安装，无法执行 SHACL 校验") from e

        # 1. 生成 SHACL shapes（实时，防漂移）
        shapes_ttl = self._shape_gen.generate(entity_types)
        shapes_graph = Graph()
        shapes_graph.parse(data=shapes_ttl, format="turtle")

        # 2. 实例 JSON → RDF 数据图
        data_graph = Graph()
        for inst in instances:
            self._instance_to_graph(data_graph, inst)

        # 3. pySHACL 校验
        try:
            from pyshacl import validate as shacl_validate
        except ImportError as e:
            raise RuntimeError("pySHACL 未安装，无法执行 SHACL 校验") from e

        conforms, results_graph, results_text = shacl_validate(
            data_graph,
            shacl_graph=shapes_graph,
            inference="none",
        )

        # 4. 提取违规明细
        results = self._extract_results(results_graph)

        return {
            "conforms": conforms,
            "results": results,
            "shape_count": len(entity_types),
            "instance_count": len(instances),
            "violation_count": len(results),
        }

    def _instance_to_graph(self, graph, inst: Dict[str, Any]) -> None:
        """单实例 → RDF 三元组。

        - properties 中的值 → 字面量（Literal）
        - links 中的值 → IRI 引用（指向目标实体，满足 sh:class 约束）
        """
        from rdflib import Literal, URIRef

        type_id = inst.get("type_id") or inst.get("type", "")
        instance_id = inst.get("instance_id") or inst.get("id") or ""
        if not type_id or not instance_id:
            return

        instance_iri = URIRef(f"{self.base_uri}instance/{instance_id}")
        type_iri = URIRef(f"{self.base_uri}{type_id}")
        graph.add((instance_iri, URIRef(RDF_TYPE), type_iri))

        # 属性 → 字面量
        props = inst.get("properties", {}) or {}
        for key, val in props.items():
            prop_iri = URIRef(f"{self.base_uri}{type_id}/{key}")
            if isinstance(val, (list, tuple)):
                for item in val:
                    graph.add((instance_iri, prop_iri, self._to_literal(item)))
            else:
                graph.add((instance_iri, prop_iri, self._to_literal(val)))

        # 关系 → IRI 引用（目标实体）
        links = inst.get("links", {}) or {}
        for key, val in links.items():
            prop_iri = URIRef(f"{self.base_uri}{type_id}/{key}")
            values = val if isinstance(val, (list, tuple)) else [val]
            for item in values:
                if not item:
                    continue
                # 目标实体 IRI（指向目标类型实例）
                target_iri = URIRef(f"{self.base_uri}instance/{item}")
                # 同时声明目标实体类型（若 val 是 dict 含 type）
                graph.add((instance_iri, prop_iri, target_iri))

    @staticmethod
    def _to_literal(val: Any):
        from rdflib import Literal
        if isinstance(val, bool):
            return Literal(val)
        if isinstance(val, int):
            return Literal(val)
        if isinstance(val, float):
            return Literal(val)
        return Literal(str(val))

    @staticmethod
    def _extract_results(results_graph) -> List[Dict[str, str]]:
        """从 pySHACL 结果图提取违规明细"""
        from rdflib import Namespace

        SH = Namespace("http://www.w3.org/ns/shacl#")
        results = []
        for subj in results_graph.subjects(SH.resultSeverity, None):
            focus = results_graph.value(subj, SH.focusNode)
            path = results_graph.value(subj, SH.resultPath)
            msg = results_graph.value(subj, SH.resultMessage)
            sev = results_graph.value(subj, SH.resultSeverity)
            results.append({
                "focus_node": str(focus) if focus else "",
                "path": str(path).split("/")[-1] if path else "",
                "message": str(msg) if msg else "",
                "severity": str(sev).split("#")[-1] if sev else "Violation",
            })
        return results


def validate_instances(
    entity_types: List[Dict[str, Any]],
    instances: List[Dict[str, Any]],
) -> Dict[str, Any]:
    """便捷函数：校验实例数据"""
    return SHACLValidator().validate(entity_types, instances)


__all__ = ["SHACLValidator", "validate_instances"]
