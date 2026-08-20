"""ShapeGenerator — 自定义 Schema → SHACL Shape 实时生成（ADR-077 §3）。

双轨制核心：SHACL Shape 由自定义 Schema 单向派生，**不持久化**，
每次 validate 请求时从当前 Schema 实时生成，杜绝陈旧副本（裁决 1）。

映射规则（ADR-077 §3）：
- required → sh:minCount 1
- data_type → sh:datatype（string/integer/float/boolean/date/datetime）
- cardinality → sh:minCount / sh:maxCount
- link_type=composition → sh:class 指向目标类型
- classification_level → sh:in 枚举
- primary_key → sh:uniqueLang（唯一性，需 SPARQL 支持的降级为 sh:minCount 1）

输出：Turtle 格式的 SHACL shapes 文本（rdflib 序列化）。
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional

# SHACL 命名空间
SH = "http://www.w3.org/ns/shacl#"
XSD = "http://www.w3.org/2001/XMLSchema#"
RDF = "http://www.w3.org/1999/02/22-rdf-syntax-ns#"
ODAP = "https://odap.local/ontology/"

# data_type → XSD 类型映射
DATA_TYPE_XSD = {
    "string": "string",
    "integer": "integer",
    "float": "double",
    "boolean": "boolean",
    "date": "date",
    "datetime": "dateTime",
    "json": "string",
    "array": "string",
}

# cardinality → (minCount, maxCount)
CARDINALITY_BOUNDS = {
    "1:1": (1, 1),
    "1:N": (1, None),
    "N:1": (0, 1),
    "N:N": (0, None),
    "N:M": (0, None),
}

CLASSIFICATION_LEVELS = ["TS", "S", "C", "U"]


class ShapeGenerator:
    """自定义 Schema 实体类型 → SHACL NodeShape 生成器"""

    def __init__(self, base_uri: str = ODAP):
        self.base_uri = base_uri

    def generate(self, entity_types: List[Dict[str, Any]]) -> str:
        """为实体类型列表生成 SHACL shapes（Turtle 文本）。

        Args:
            entity_types: EntityTypeDefinition 的 dict 列表

        Returns:
            Turtle 序列化的 SHACL shapes
        """
        shapes: List[str] = []
        for et in entity_types:
            shapes.append(self._entity_type_shape(et))
        return "\n".join(shapes)

    def _entity_type_shape(self, et: Dict[str, Any]) -> str:
        """生成单个实体类型的 NodeShape"""
        type_id = et.get("type_id") or et.get("name", "Unknown")
        type_iri = f"{self.base_uri}{type_id}"
        shape_iri = f"{self.base_uri}{type_id}Shape"

        lines: List[str] = []
        lines.append(f"<{shape_iri}>")
        lines.append(f"    a <{SH}NodeShape> ;")
        lines.append(f"    <{SH}targetClass> <{type_iri}> ;")

        props = et.get("properties", []) or []
        prop_triples = self._property_triples(props, type_id)
        link_triples = self._link_triples(et.get("links", []) or [], type_id)
        prop_names = [p.get("name", "") for p in props]
        pk_triples = self._primary_key_triples(
            et.get("primary_key", []) or [], type_id, prop_names
        )

        if prop_triples or link_triples or pk_triples:
            lines.append(f"    <{SH}property>")
            all_constraints = prop_triples + link_triples + pk_triples
            for i, (prop_iri, constraints) in enumerate(all_constraints):
                lines.append(f"        [ a <{SH}PropertyShape> ;")
                lines.append(f"          <{SH}path> <{prop_iri}> ;")
                for j, constraint in enumerate(constraints):
                    sep = " ;" if j < len(constraints) - 1 else ""
                    lines.append(f"          {constraint}{sep}")
                # 若该 property shape 还有后续，用 , 连接；否则 ] 收尾
                if i < len(all_constraints) - 1:
                    lines.append("        ] ,")
                else:
                    lines.append("        ]")
            lines.append("    .")
        else:
            # 无属性约束，直接收尾
            lines[-1] = f"    <{SH}targetClass> <{type_iri}> ."

        lines.append("")
        return "\n".join(lines)

    def _property_triples(self, props: List[Dict[str, Any]], type_id: str) -> List[tuple]:
        """属性 → (path_iri, [constraint_str, ...])"""
        result = []
        for p in props:
            name = p.get("name", "")
            prop_iri = f"{self.base_uri}{type_id}/{name}"
            constraints = []

            if p.get("required"):
                constraints.append(f"<{SH}minCount> 1")

            dt = p.get("data_type", "string")
            xsd_type = DATA_TYPE_XSD.get(dt, "string")
            constraints.append(f"<{SH}datatype> <{XSD}{xsd_type}>")

            # 注意：classification_level 是属性的密级**元数据**，不是值的枚举约束，
            # 不映射为 sh:in（密级枚举校验属数据分类模块职责，见 ADR-077 §5 边界）。

            if constraints:
                result.append((prop_iri, constraints))
        return result

    def _link_triples(self, links: List[Dict[str, Any]], type_id: str) -> List[tuple]:
        """关系 → (path_iri, [constraint_str, ...])"""
        result = []
        for link in links:
            name = link.get("name", "")
            target = link.get("target_type", "")
            prop_iri = f"{self.base_uri}{type_id}/{name}"
            constraints = []

            card = link.get("cardinality", "1:N")
            if isinstance(card, dict):
                card = card.get("value", "1:N")
            min_c, max_c = CARDINALITY_BOUNDS.get(card, (0, None))
            if min_c is not None:
                constraints.append(f"<{SH}minCount> {min_c}")
            if max_c is not None:
                constraints.append(f"<{SH}maxCount> {max_c}")

            link_type = link.get("link_type", "association")
            if isinstance(link_type, dict):
                link_type = link_type.get("value", "association")
            if link_type == "composition" and target:
                # 组合关系：目标必须是 IRI 节点（sh:nodeKind sh:IRI），
                # 避免要求目标实例额外声明 rdf:type 的复杂度（ADR-077 §3）
                constraints.append(f"<{SH}nodeKind> <{SH}IRI>")

            if constraints:
                result.append((prop_iri, constraints))
        return result

    def _primary_key_triples(
        self, primary_keys: List[str], type_id: str, property_names: List[str]
    ) -> List[tuple]:
        """主键 → 唯一性约束（降级为 minCount 1 保证存在）。

        跳过已在 properties 中定义的字段，避免与 property shape 的 path 重复
        （重复 path 会导致 pySHACL 解析异常）。
        """
        result = []
        existing = set(property_names)
        for pk in primary_keys:
            if pk in existing:
                continue
            prop_iri = f"{self.base_uri}{type_id}/{pk}"
            result.append((prop_iri, [f"<{SH}minCount> 1"]))
        return result


def generate_shapes(entity_types: List[Dict[str, Any]]) -> str:
    """便捷函数：生成 SHACL shapes Turtle 文本"""
    return ShapeGenerator().generate(entity_types)


__all__ = ["ShapeGenerator", "generate_shapes"]
