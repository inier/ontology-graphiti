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

ADR-085 D2/F7-b 扩展（约束以**参数**传入，本类保持纯净、不 import semantic_admin，
守 import-linter C3）：
- usl_cardinalities(min_card,max_card,domain_term,range_term,rel_name)
    → 在 domain_term 对应 NodeShape 上追加 property shape：
      sh:minCount/sh:maxCount + sh:class 指向 range_term。
- usl_disjoint_pairs(term_a,term_b) 与 L6 disjoint_classes(subject,object)
    → 两个 term 的 NodeShape 各追加 sh:not [ sh:class 对方 ]（对称、按对去重）。
  说明：L6 的 object_property_cardinality / domain / range / sub_class_of 公理
  **不带 domain 类**（subject 是关系短语），无法定位到具体 NodeShape，故本切片
  不据其派生焦点节点约束（避免猜测性反推，规则 14.4）；它们已持久化，供 G2.2
  真值与治理飞轮消费。

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

    def generate(
        self,
        entity_types: List[Dict[str, Any]],
        *,
        cardinalities: Optional[List[Dict[str, Any]]] = None,
        disjoint_pairs: Optional[List[Dict[str, Any]]] = None,
        axioms: Optional[List[Dict[str, Any]]] = None,
    ) -> str:
        """为实体类型列表生成 SHACL shapes（Turtle 文本）。

        Args:
            entity_types: EntityTypeDefinition 的 dict 列表
            cardinalities: usl_cardinalities 行（rel_name/domain_term/range_term/
                min_card/max_card），按 domain_term 挂到对应 NodeShape（ADR-085 D2）
            disjoint_pairs: usl_disjoint_pairs 行（term_a/term_b）→ sh:not
            axioms: L6 公理；仅 disjoint_classes 进不相交通道（ADR-085 D2）

        Returns:
            Turtle 序列化的 SHACL shapes
        """
        card_by_domain = self._index_cardinalities(cardinalities)
        disjoint_by_term = self._index_disjoint(disjoint_pairs, axioms)
        shapes: List[str] = []
        for et in entity_types:
            shapes.append(
                self._entity_type_shape(et, card_by_domain, disjoint_by_term)
            )
        return "\n".join(shapes)

    def _entity_type_shape(
        self,
        et: Dict[str, Any],
        card_by_domain: Optional[Dict[str, List[Dict[str, Any]]]] = None,
        disjoint_by_term: Optional[Dict[str, List[str]]] = None,
    ) -> str:
        """生成单个实体类型的 NodeShape"""
        card_by_domain = card_by_domain or {}
        disjoint_by_term = disjoint_by_term or {}
        type_id = et.get("type_id") or et.get("name", "Unknown")
        type_iri = f"{self.base_uri}{type_id}"
        shape_iri = f"{self.base_uri}{type_id}Shape"
        key = str(type_id).lower()

        props = et.get("properties", []) or []
        prop_triples = self._property_triples(props, type_id)
        link_triples = self._link_triples(et.get("links", []) or [], type_id)
        prop_names = [p.get("name", "") for p in props]
        pk_triples = self._primary_key_triples(
            et.get("primary_key", []) or [], type_id, prop_names
        )
        # ADR-085 D2/F7-b：usl_cardinalities 派生的关系基数 property shapes
        card_triples = self._cardinality_triples(
            card_by_domain.get(key, []), type_id
        )
        all_constraints = prop_triples + link_triples + pk_triples + card_triples
        # ADR-085 D2/F7-b：usl_disjoint_pairs + L6 disjoint_classes 派生的 sh:not
        not_iris = disjoint_by_term.get(key, [])

        # 顶层谓词分段：targetClass + 0..n 个 sh:not + 可选 sh:property 块。
        # 除最后一段以 " ." 收尾外，其余以 " ;" 连接（统一终止符，避免分隔错配）。
        lines: List[str] = [f"<{shape_iri}>", f"    a <{SH}NodeShape> ;"]
        statements: List[List[str]] = [
            [f"    <{SH}targetClass> <{type_iri}>"]
        ]
        for other_iri in not_iris:
            statements.append(
                [f"    <{SH}not> [ a <{SH}NodeShape> ; <{SH}class> <{other_iri}> ]"]
            )
        if all_constraints:
            block = [f"    <{SH}property>"]
            for i, (prop_iri, constraints) in enumerate(all_constraints):
                block.append(f"        [ a <{SH}PropertyShape> ;")
                block.append(f"          <{SH}path> <{prop_iri}> ;")
                for j, constraint in enumerate(constraints):
                    sep = " ;" if j < len(constraints) - 1 else ""
                    block.append(f"          {constraint}{sep}")
                block.append("        ]" + (" ," if i < len(all_constraints) - 1 else ""))
            statements.append(block)
        for idx, stmt in enumerate(statements):
            stmt[-1] = stmt[-1] + (" ." if idx == len(statements) - 1 else " ;")
            lines.extend(stmt)

        lines.append("")
        return "\n".join(lines)

    def _cardinality_triples(
        self, cards: List[Dict[str, Any]], type_id: str
    ) -> List[tuple]:
        """usl_cardinalities 行 → (path_iri, [constraint_str, ...])。

        path 沿用关系约定 `{base}{type_id}/{rel_name}`；range_term → sh:class。
        min_card/max_card 为 None 时不派生对应 count（无下限/无上限）。
        """
        result: List[tuple] = []
        for c in cards:
            rel = str(c.get("rel_name") or "").strip()
            if not rel:
                continue
            prop_iri = f"{self.base_uri}{type_id}/{rel}"
            constraints: List[str] = []
            min_c = c.get("min_card")
            max_c = c.get("max_card")
            if min_c is not None:
                constraints.append(f"<{SH}minCount> {int(min_c)}")
            if max_c is not None:
                constraints.append(f"<{SH}maxCount> {int(max_c)}")
            range_term = str(c.get("range_term") or "").strip()
            if range_term:
                constraints.append(f"<{SH}class> <{self.base_uri}{range_term}>")
            if constraints:
                result.append((prop_iri, constraints))
        return result

    @staticmethod
    def _index_cardinalities(
        cardinalities: Optional[List[Dict[str, Any]]],
    ) -> Dict[str, List[Dict[str, Any]]]:
        """按 lower(domain_term) 归组基数行（匹配实体类型 type_id/name 的小写键）。"""
        idx: Dict[str, List[Dict[str, Any]]] = {}
        for c in cardinalities or []:
            if not isinstance(c, dict):
                continue
            domain = str(c.get("domain_term") or "").strip().lower()
            if not domain:
                continue
            idx.setdefault(domain, []).append(c)
        return idx

    def _index_disjoint(
        self,
        disjoint_pairs: Optional[List[Dict[str, Any]]],
        axioms: Optional[List[Dict[str, Any]]],
    ) -> Dict[str, List[str]]:
        """合并 usl_disjoint_pairs + L6 disjoint_classes → {lower(term): [对方 IRI, ...]}。

        对称展开（a→b 且 b→a），按 (a,b) 小写对去重（双源同一对不翻倍）。
        IRI 用术语**原大小写**（与 NodeShape 的 sh:class/targetClass IRI 一致），
        仅查找键用小写。
        """
        orig: Dict[str, str] = {}
        edges: set = set()

        def _add(a: Any, b: Any) -> None:
            sa = str(a or "").strip()
            sb = str(b or "").strip()
            if not sa or not sb or sa == sb:
                return
            orig.setdefault(sa.lower(), sa)
            orig.setdefault(sb.lower(), sb)
            edges.add((sa.lower(), sb.lower()))

        for d in disjoint_pairs or []:
            if isinstance(d, dict):
                _add(d.get("term_a"), d.get("term_b"))
        for ax in axioms or []:
            if isinstance(ax, dict) and str(ax.get("axiom_type") or "") == "disjoint_classes":
                _add(ax.get("subject"), ax.get("object"))

        idx: Dict[str, set] = {}
        for a, b in edges:
            idx.setdefault(a, set()).add(f"{self.base_uri}{orig[b]}")
            idx.setdefault(b, set()).add(f"{self.base_uri}{orig[a]}")
        return {k: sorted(v) for k, v in idx.items()}


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
