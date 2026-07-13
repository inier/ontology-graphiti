"""L6 Axiom Deriver — 5 类 OWL 风格公理推导。

Supported axiom types (语义与 OWL 对齐，命名 snake_case)：
  1. sub_class_of(A, B)              — A ⊑ B (传递闭包 closure from L2/L3 is_a edges)
  2. disjoint_classes(A, B)          — A ∩ B ≡ ∅ (sibling + conflict features)
  3. object_property_domain(R, A)    — ∀ R.T  domain = A
  4. object_property_range(R, B)     — ∀ T.R  range  = B
  5. object_property_cardinality(R, min, max) — ≥min / ≤max / =n 约束
  6. data_property_cardinality(P, min, max)   — 属性类型(is attribute_of)的基数

输入（来自 L1~L5 产物的聚合视图）：
  - hierarchy: [{"child": str, "parent": str, "relation_type" == "is_a" 默认, "confidence"? float}]
  - relations: [{"subject_canonical", "object_canonical", "relation_type",
                 "relation_phrase"? str, "source_count"? int (default 1),
                 "semantic_type"? str}]
  - disjoint_pair_hints?: [{"a": str, "b": str, "reason": str, "confidence"? float}]
  - term_semantic_types?: {canonical: str}  用于 attribute_of → data_property_cardinality 分支

零依赖，纯逻辑推导。≤ 250 LOC。
"""

from __future__ import annotations

from collections import defaultdict
from typing import Any, Dict, Iterable, List, Optional, Tuple


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------
class AxiomDeriver:
    """OWL 5 类公理推导器。"""

    def __init__(self, *, sibling_disjoint_confidence: float = 0.7) -> None:
        self.sibling_disjoint_confidence = float(sibling_disjoint_confidence or 0.0)

    # ------------------------------------------------------------------
    def derive(
        self,
        *,
        hierarchy: Iterable[Dict[str, Any]],
        relations: Iterable[Dict[str, Any]],
        disjoint_pair_hints: Optional[Iterable[Dict[str, Any]]] = None,
        term_semantic_types: Optional[Dict[str, str]] = None,
    ) -> Dict[str, Any]:
        """返回所有公理 + 计数统计。"""
        axioms: List[Dict[str, Any]] = []
        h = list(hierarchy or [])
        r = list(relations or [])
        tst = dict(term_semantic_types or {})
        # (1) sub_class_of (直接 + 传递闭包非直接边)
        sub_edges, parents_map, children_map = self._sub_class_of_direct(h)
        axioms.extend(sub_edges)
        trans_edges = self._sub_class_of_transitive(parents_map, children_map, sub_edges)
        axioms.extend(trans_edges)
        # (2) disjoint_classes (siblings disjoint + hints)
        axioms.extend(self._disjoint_classes(children_map, disjoint_pair_hints or []))
        # (3/4) domain/range
        axioms.extend(self._domain_range(r))
        # (5/6) cardinality (object / data 属性基数)
        axioms.extend(self._cardinality(r, tst))
        # 类型统计
        cnt: Dict[str, int] = defaultdict(int)
        for a in axioms:
            cnt[a["axiom_type"]] += 1
        return {
            "axioms": axioms,
            "total": len(axioms),
            "counts_by_type": dict(cnt),
        }

    # ------------------------------------------------------------------
    # (1) subClassOf
    # ------------------------------------------------------------------
    @staticmethod
    def _sub_class_of_direct(
        hierarchy: List[Dict[str, Any]],
    ) -> Tuple[List[Dict[str, Any]], Dict[str, set], Dict[str, set]]:
        axioms: List[Dict[str, Any]] = []
        parents_map: Dict[str, set] = defaultdict(set)
        children_map: Dict[str, set] = defaultdict(set)
        seen: set = set()
        for e in hierarchy:
            c = str(e.get("child") or "").strip()
            p = str(e.get("parent") or "").strip()
            if not c or not p or c == p:
                continue
            key = (c, p)
            if key in seen:
                continue
            seen.add(key)
            parents_map[c].add(p)
            children_map[p].add(c)
            conf = float(e.get("confidence") or 0.9)
            axioms.append({
                "axiom_type": "sub_class_of",
                "subject": c,
                "object": p,
                "confidence": round(min(1.0, conf), 3),
                "source": "hierarchy_direct",
                "proof": {"direct_edge": True},
            })
        return axioms, dict(parents_map), dict(children_map)

    @staticmethod
    def _sub_class_of_transitive(
        parents_map: Dict[str, set],
        children_map: Dict[str, set],
        direct_axioms: List[Dict[str, Any]],
    ) -> List[Dict[str, Any]]:
        """DFS BFS 式：对每个 c，找所有祖先（去重排直接边）。"""
        # 所有直接边
        direct_set = set()
        for a in direct_axioms:
            direct_set.add((a["subject"], a["object"]))
        trans: List[Dict[str, Any]] = []
        added: set = set()
        nodes: set = set(parents_map.keys()) | set(children_map.keys())
        for c in nodes:
            # BFS 向上找所有祖先
            stack: List[str] = list(parents_map.get(c, set()))
            visited: set = set(stack)
            ancestors: List[str] = []
            while stack:
                p = stack.pop()
                ancestors.append(p)
                for gp in parents_map.get(p, set()):
                    if gp not in visited:
                        visited.add(gp)
                        stack.append(gp)
            # 非直接的 ancestor 出公理
            for p in ancestors:
                if (c, p) in direct_set:
                    continue
                if (c, p) in added:
                    continue
                added.add((c, p))
                # 置信度：直接边 min 乘 0.9^(depth-1)
                trans.append({
                    "axiom_type": "sub_class_of",
                    "subject": c,
                    "object": p,
                    "confidence": 0.8,
                    "source": "hierarchy_transitive_closure",
                    "proof": {"direct_edge": False, "closure": True},
                })
        return trans

    # ------------------------------------------------------------------
    # (2) disjoint classes
    # ------------------------------------------------------------------
    def _disjoint_classes(
        self,
        children_map: Dict[str, set],
        hints: Iterable[Dict[str, Any]],
    ) -> List[Dict[str, Any]]:
        axioms: List[Dict[str, Any]] = []
        seen: set = set()
        # sibling disjoint：同一个 parent 下不同 child 两两不相交
        for _, children in children_map.items():
            lst = sorted(children)
            n = len(lst)
            for i in range(n):
                for j in range(i + 1, n):
                    a, b = lst[i], lst[j]
                    key = tuple(sorted((a, b)))
                    if key in seen:
                        continue
                    seen.add(key)
                    axioms.append({
                        "axiom_type": "disjoint_classes",
                        "subject": a,
                        "object": b,
                        "confidence": self.sibling_disjoint_confidence,
                        "source": "sibling_disjoint",
                        "proof": {"siblings_of_common_parent": True},
                    })
        # hints
        for h in hints or []:
            a = str(h.get("a") or "").strip()
            b = str(h.get("b") or "").strip()
            if not a or not b or a == b:
                continue
            key = tuple(sorted((a, b)))
            if key in seen:
                continue
            seen.add(key)
            conf = float(h.get("confidence") or 0.85)
            axioms.append({
                "axiom_type": "disjoint_classes",
                "subject": a,
                "object": b,
                "confidence": round(min(1.0, conf), 3),
                "source": "explicit_hint",
                "proof": {"hint_reason": str(h.get("reason") or "")},
            })
        return axioms

    # ------------------------------------------------------------------
    # (3/4) domain/range：按 relation_phrase 聚合（同一个关系短语共享 domain/range）
    # ------------------------------------------------------------------
    @staticmethod
    def _domain_range(relations: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        axioms: List[Dict[str, Any]] = []
        subj_by_rel: Dict[str, Dict[str, int]] = defaultdict(lambda: defaultdict(int))
        obj_by_rel: Dict[str, Dict[str, int]] = defaultdict(lambda: defaultdict(int))
        total_by_rel: Dict[str, int] = defaultdict(int)
        for r in relations:
            rp = str(r.get("relation_phrase") or r.get("canonical") or "").strip()
            s = str(r.get("subject_canonical") or "").strip()
            o = str(r.get("object_canonical") or "").strip()
            if not rp or not s or not o:
                continue
            w = int(r.get("source_count") or 1)
            subj_by_rel[rp][s] += w
            obj_by_rel[rp][o] += w
            total_by_rel[rp] += w
        for rp, total in total_by_rel.items():
            # domain: top-1 占比 ≥ 0.6
            top_s, s_cnt = AxiomDeriver._top1(subj_by_rel[rp])
            if top_s and s_cnt / total >= 0.6:
                axioms.append({
                    "axiom_type": "object_property_domain",
                    "subject": rp,
                    "object": top_s,
                    "confidence": round(s_cnt / total, 3),
                    "source": "relation_domain_majority",
                    "proof": {"support": s_cnt, "total": total, "ratio": round(s_cnt / total, 3)},
                })
            # range
            top_o, o_cnt = AxiomDeriver._top1(obj_by_rel[rp])
            if top_o and o_cnt / total >= 0.6:
                axioms.append({
                    "axiom_type": "object_property_range",
                    "subject": rp,
                    "object": top_o,
                    "confidence": round(o_cnt / total, 3),
                    "source": "relation_range_majority",
                    "proof": {"support": o_cnt, "total": total, "ratio": round(o_cnt / total, 3)},
                })
        return axioms

    # ------------------------------------------------------------------
    # (5/6) cardinality
    # ------------------------------------------------------------------
    @staticmethod
    def _cardinality(
        relations: List[Dict[str, Any]],
        term_semantic_types: Dict[str, str],
    ) -> List[Dict[str, Any]]:
        axioms: List[Dict[str, Any]] = []
        # per (subj, relation_phrase) ——> distinct objs count list
        objcount_per_relsubj: Dict[Tuple[str, str], int] = defaultdict(int)
        per_rel: Dict[str, List[int]] = defaultdict(list)
        for r in relations:
            rp = str(r.get("relation_phrase") or r.get("canonical") or "").strip()
            s = str(r.get("subject_canonical") or "").strip()
            o = str(r.get("object_canonical") or "").strip()
            if not rp or not s or not o:
                continue
            objcount_per_relsubj[(s, rp)] += 1
        for (s, rp), cnt in objcount_per_relsubj.items():
            per_rel[rp].append(cnt)
        for rp, cnts in per_rel.items():
            if not cnts:
                continue
            lo = min(cnts)
            hi = max(cnts)
            # 判断 data vs object：如果 relation_type 是 attribute_of 或 object 是 "属性类型"
            sample_rel = next(
                (x for x in relations
                 if (str(x.get("relation_phrase") or x.get("canonical") or "")) == rp),
                None,
            )
            rt = str((sample_rel or {}).get("relation_type") or "").strip()
            obj_type = ""
            obj_c = str((sample_rel or {}).get("object_canonical") or "").strip()
            if obj_c:
                obj_type = str(term_semantic_types.get(obj_c) or "").strip()
            if rt == "attribute_of" or obj_type == "属性类型":
                ax_type = "data_property_cardinality"
            else:
                ax_type = "object_property_cardinality"
            # 如果 lo == hi，就是 functional（=n）；否则 [lo, hi]
            conf = 0.75 if lo == hi else 0.65
            axioms.append({
                "axiom_type": ax_type,
                "subject": rp,
                "object": "",
                "min_card": int(lo),
                "max_card": int(hi),
                "confidence": conf,
                "source": "frequency_based_cardinality",
                "proof": {"per_subject_object_counts": sorted(cnts), "sample_size": len(cnts)},
            })
        return axioms

    # ------------------------------------------------------------------
    @staticmethod
    def _top1(d: Dict[str, int]) -> Tuple[str, int]:
        if not d:
            return "", 0
        best_k = ""
        best_v = -1
        for k, v in d.items():
            if v > best_v:
                best_v = v
                best_k = k
        return best_k, best_v
