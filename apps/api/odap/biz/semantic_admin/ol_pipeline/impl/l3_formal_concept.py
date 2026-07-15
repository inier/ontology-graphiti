"""L3 Formal Concept Analysis — 形式概念分析 FCA（精简纯逻辑版，零依赖）。

输入：候选术语(entities) + 属性(property_specs 或自定义属性表)
输出：formal_concepts 列表（概念格，extent/intent/stability）+ 建议新层级边

Approach：
  1. 构造形式背景 K=(G, M, I)：
     - G = entities（entity canonical label，≤ 200 个）
     - M = attributes（属性名或同义词/语义类型 token，≤ 200 个）
     - I(g, m) = True if 属性 m 被对象 g 具有
  2. 用 Norusis 简化算法（枚举所有对象子集的闭合 → 去重 → 按 intent 排序）
     不要求完全正确的 Hasse 图，仅需要输出稳定概念（stability ≥ 0.6）
  3. 概念格去重 + stability 计算
  4. 建议新层级边：parent concept(extent) ⊇ child concept(extent)

参考：FCA 标准定义。对 Zoo/Animal 10 对象 × 8 属性规模，计算复杂度 ≤ O(2^min(|G|,|M|))，
实际使用 "只闭合 top-k 属性频率词" 近似（TOPK_ATTR=128），避免指数爆炸。
"""

from __future__ import annotations

from itertools import combinations
from typing import Any, Dict, List, Tuple

TOPK_ATTR_DEFAULT = 128
MIN_EXTENT_DEFAULT = 1
MAX_CONCEPTS_DEFAULT = 500


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------
class FormalConceptAnalyzer:
    """FCA 概念格生成器。

    公开方法：
      analyze(
          entity_attributes: List[Dict[str, Any]],
          *,
          entity_field: str = "canonical",
          attribute_fields: Tuple[str, ...] = ("semantic_type", "synonyms", "domain_id"),
          min_stability: float = 0.6,
          topk_attr: int = TOPK_ATTR_DEFAULT,
          max_concepts: int = MAX_CONCEPTS_DEFAULT,
      ) -> Dict:  # {"concepts": [...], "suggested_hierarchy_edges": [...]}
    """

    # ------------------------------------------------------------------
    def analyze(
        self,
        entity_attributes: List[Dict[str, Any]],
        *,
        entity_field: str = "canonical",
        attribute_fields: Tuple[str, ...] = (
            "semantic_type",
            "synonyms",
            "domain_id",
            "definition",
        ),
        min_stability: float = 0.6,
        topk_attr: int = TOPK_ATTR_DEFAULT,
        max_concepts: int = MAX_CONCEPTS_DEFAULT,
    ) -> Dict[str, Any]:
        """FCA 主入口。"""
        if not entity_attributes:
            return {
                "formal_concepts": [],
                "suggested_hierarchy_edges": [],
                "lattice_count": 0,
                "context_size": {"objects": 0, "attributes": 0, "incidence": 0},
            }
        # Step 1: Build formal context K=(G,M,I)
        g_list, m_list, incidence_matrix = self._build_context(
            entity_attributes,
            entity_field=entity_field,
            attribute_fields=attribute_fields,
            topk_attr=topk_attr,
        )
        if not g_list or not m_list:
            return {
                "formal_concepts": [],
                "suggested_hierarchy_edges": [],
                "lattice_count": 0,
                "context_size": {
                    "objects": len(g_list),
                    "attributes": len(m_list),
                    "incidence": 0,
                },
            }
        # Step 2: Enumerate concepts (Bordat style — attribute-based closure)
        concepts = self._bordnet_attribute_concepts(
            g_list, m_list, incidence_matrix,
            max_concepts=max_concepts,
        )
        # Step 3: Filter by stability
        filtered = []
        for c in concepts:
            ext_size = bin(c["extent_mask"]).count("1")
            int_size = bin(c["intent_mask"]).count("1")
            if ext_size == 0 or int_size == 0:
                continue
            if self._stability(c, incidence_matrix, len(g_list)) >= float(min_stability or 0.0):
                c["_ext_size"] = ext_size
                c["_int_size"] = int_size
                filtered.append(c)
        filtered.sort(key=lambda c: (-c["_int_size"], c["_ext_size"]))
        # Step 4: Build suggested hierarchy edges (parent ⊃ child, 直接子概念)
        edges = self._direct_children_edges(filtered)
        return {
            "formal_concepts": [self._to_public(c, g_list, m_list) for c in filtered],
            "suggested_hierarchy_edges": edges,
            "lattice_count": len(filtered),
            "context_size": {
                "objects": len(g_list),
                "attributes": len(m_list),
                "incidence": sum(sum(row) for row in incidence_matrix),
            },
        }

    # ------------------------------------------------------------------
    # Step 1: Build K=(G,M,I)
    # ------------------------------------------------------------------
    @staticmethod
    def _build_context(
        entity_attributes: List[Dict[str, Any]],
        *,
        entity_field: str,
        attribute_fields: Tuple[str, ...],
        topk_attr: int,
    ) -> Tuple[List[str], List[str], List[List[int]]]:
        g_list: List[str] = []
        g_to_idx: Dict[str, int] = {}
        m_freq: Dict[str, int] = {}
        # 临时记录每个 entity 拥有的 attrs（用 set 去重）
        g_attrs: List[set] = []
        for e in entity_attributes:
            name = str(e.get(entity_field) or "")
            if not name:
                continue
            if name in g_to_idx:
                # 重复：合并属性
                idx = g_to_idx[name]
            else:
                idx = len(g_list)
                g_list.append(name)
                g_to_idx[name] = idx
                g_attrs.append(set())
            # 扫 attribute_fields: scalar 当 attribute名=value；list/dict 展开
            for fld in attribute_fields:
                v = e.get(fld)
                if v is None or v == "":
                    continue
                tokens = FormalConceptAnalyzer._flatten_to_atoms(fld, v)
                for tok in tokens:
                    key = f"{fld}::{tok}"
                    g_attrs[idx].add(key)
                    m_freq[key] = m_freq.get(key, 0) + 1
        if not g_list:
            return [], [], []
        # Top-k attr: 按 freq desc 截断
        sorted_attrs = sorted(m_freq.items(), key=lambda kv: (-kv[1], kv[0]))
        if len(sorted_attrs) > topk_attr:
            allowed = set(k for k, _ in sorted_attrs[:topk_attr])
        else:
            allowed = set(k for k, _ in sorted_attrs)
        m_list: List[str] = [k for k, _ in sorted_attrs if k in allowed]
        m_to_idx = {m: i for i, m in enumerate(m_list)}
        # incidence matrix: 0/1 ints
        n = len(g_list)
        incidence: List[List[int]] = [[0] * len(m_list) for _ in range(n)]
        for i, s in enumerate(g_attrs):
            for a in s:
                if a in m_to_idx:
                    incidence[i][m_to_idx[a]] = 1
        return g_list, m_list, incidence

    # ------------------------------------------------------------------
    @staticmethod
    def _flatten_to_atoms(field: str, v: Any) -> List[str]:
        """把任意结构变成若干原子字符串。"""
        out: List[str] = []
        if isinstance(v, (list, tuple, set)):
            for x in v:
                out.extend(FormalConceptAnalyzer._flatten_to_atoms(field, x))
        elif isinstance(v, dict):
            for k, val in v.items():
                out.append(str(k))
                out.extend(FormalConceptAnalyzer._flatten_to_atoms(f"{field}.{k}", val))
        else:
            s = str(v).strip()
            if 0 < len(s) <= 64:
                out.append(s)
        return out

    # ------------------------------------------------------------------
    # Step 2: Bordat attribute concept enumeration (近似版，避免指数爆炸)
    # ------------------------------------------------------------------
    @staticmethod
    def _bordnet_attribute_concepts(
        g_list: List[str],
        m_list: List[str],
        I_matrix: List[List[int]],
        *,
        max_concepts: int,
    ) -> List[Dict[str, Any]]:
        """从每个属性出发做闭包，加上若干随机属性组合闭包，去重。"""
        n_g = len(g_list)
        n_m = len(m_list)
        concept_set: set = set()
        concepts: List[Dict[str, Any]] = []

        def add_concept(extent_mask: int) -> None:
            if extent_mask in concept_set:
                return
            if len(concepts) >= max_concepts:
                return
            intent_mask = FormalConceptAnalyzer._intent_from_extent(
                extent_mask, I_matrix, n_g, n_m
            )
            # 再闭合一次 extent ← intent，保证是概念
            closed_extent = FormalConceptAnalyzer._extent_from_intent(
                intent_mask, I_matrix, n_g
            )
            if closed_extent in concept_set:
                return
            concept_set.add(closed_extent)
            concepts.append({
                "extent_mask": closed_extent,
                "intent_mask": FormalConceptAnalyzer._intent_from_extent(
                    closed_extent, I_matrix, n_g, n_m
                ),
            })

        # 概念：全对象底
        add_concept((1 << n_g) - 1)
        # 概念：每个属性的闭包
        for j in range(n_m):
            j_mask = 1 << j
            ext = FormalConceptAnalyzer._extent_from_intent(j_mask, I_matrix, n_g)
            if ext:
                add_concept(ext)
        # 概念：两两属性组合（避免爆炸：前 32 个高频属性）
        combo_limit = min(n_m, 32)
        for a, b in combinations(range(combo_limit), 2):
            j_mask = (1 << a) | (1 << b)
            ext = FormalConceptAnalyzer._extent_from_intent(j_mask, I_matrix, n_g)
            if ext:
                add_concept(ext)
        # 概念：top 64 attrs 三三组合（限制数量）
        if len(concepts) < max_concepts - 80:
            combo_limit_3 = min(n_m, 16)
            for combo in combinations(range(combo_limit_3), 3):
                if len(concepts) >= max_concepts:
                    break
                j_mask = 0
                for j in combo:
                    j_mask |= (1 << j)
                ext = FormalConceptAnalyzer._extent_from_intent(j_mask, I_matrix, n_g)
                if ext:
                    add_concept(ext)
        return concepts

    # ------------------------------------------------------------------
    @staticmethod
    def _extent_from_intent(intent_mask: int, I_matrix: List[List[int]], n_g: int) -> int:
        """g ∈ extent ↔ ∀ m ∈ intent, g I m"""
        m_list_in_intent = [j for j in range(64) if (intent_mask >> j) & 1]
        if not m_list_in_intent:
            return (1 << n_g) - 1
        ext = 0
        for i in range(n_g):
            if all(I_matrix[i][j] for j in m_list_in_intent):
                ext |= (1 << i)
        return ext

    @staticmethod
    def _intent_from_extent(
        extent_mask: int, I_matrix: List[List[int]], _n_g: int, n_m: int
    ) -> int:
        """m ∈ intent ↔ ∀ g ∈ extent, g I m"""
        g_list_in_extent = [i for i in range(64) if (extent_mask >> i) & 1]
        if not g_list_in_extent:
            return (1 << n_m) - 1
        intent = 0
        for j in range(n_m):
            if all(I_matrix[i][j] for i in g_list_in_extent):
                intent |= (1 << j)
        return intent

    # ------------------------------------------------------------------
    # Step 3: Stability (Separation + Separation index 简化版: |extent_subsets_share_same_intent| / 2^|extent|)
    # ------------------------------------------------------------------
    @staticmethod
    def _stability(
        c: Dict[str, Any],
        I_matrix: List[List[int]],
        n_g: int,
    ) -> float:
        em = int(c["extent_mask"])
        im = int(c["intent_mask"])
        # 列出 extent 中的对象索引
        eg = [i for i in range(n_g) if (em >> i) & 1]
        k = len(eg)
        if k == 0:
            return 0.0
        if k >= 18:
            # 太大，用近似：去掉每个 g 单独 closure 是否等于 intent
            same = 0
            for g in eg:
                submask = em & ~(1 << g)
                if not submask:
                    continue
                # closure(submask) 的 intent
                cl = FormalConceptAnalyzer._intent_from_extent(
                    submask, I_matrix, n_g, len(I_matrix[0]),
                )
                if cl == im:
                    same += 1
            return 1.0 - min(1.0, same / max(1, k))
        # 精确：枚举所有 2^k - 2 非空真子集（如果 k ≤ 12 全枚举；否则 sample）
        if k <= 12:
            total = 1 << k
            cnt = 0
            for r in range(1, k):
                for combo in combinations(range(k), r):
                    submask = 0
                    for idx in combo:
                        submask |= (1 << eg[idx])
                    if FormalConceptAnalyzer._intent_from_extent(
                        submask, I_matrix, n_g, len(I_matrix[0]),
                    ) == im:
                        cnt += 1
            return cnt / (total - 2) if total > 2 else 1.0
        # 近似采样 256 个子集
        samples = 256
        import random
        rng = random.Random(1234)
        cnt = 0
        for _ in range(samples):
            submask = 0
            while not submask or submask == em:
                sz = rng.randint(1, k - 1) if k > 1 else 1
                picked = rng.sample(range(k), sz)
                submask = 0
                for idx in picked:
                    submask |= (1 << eg[idx])
            if FormalConceptAnalyzer._intent_from_extent(
                submask, I_matrix, n_g, len(I_matrix[0]),
            ) == im:
                cnt += 1
        return cnt / samples

    # ------------------------------------------------------------------
    # Step 4: 直接子概念边
    # ------------------------------------------------------------------
    @staticmethod
    def _direct_children_edges(concepts: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        edges: List[Dict[str, Any]] = []
        n = len(concepts)
        for c in range(n):
            child_ext = concepts[c]["extent_mask"]
            child_size = bin(child_ext).count("1")
            # 找最近的 parent（严格超集，且没有中间概念）
            best_parents: List[int] = []
            best_size_diff = None
            for p in range(n):
                if p == c:
                    continue
                par_ext = concepts[p]["extent_mask"]
                if (par_ext & child_ext) != child_ext or par_ext == child_ext:
                    continue
                par_size = bin(par_ext).count("1")
                diff = par_size - child_size
                if diff <= 0:
                    continue
                # 中间概念？
                intermediate = False
                for m in range(n):
                    if m == c or m == p:
                        continue
                    mid_ext = concepts[m]["extent_mask"]
                    if (
                        (mid_ext & child_ext) == child_ext
                        and (par_ext & mid_ext) == mid_ext
                        and mid_ext != child_ext
                        and mid_ext != par_ext
                    ):
                        intermediate = True
                        break
                if intermediate:
                    continue
                if best_size_diff is None or diff < best_size_diff:
                    best_parents = [p]
                    best_size_diff = diff
                elif diff == best_size_diff:
                    best_parents.append(p)
            for p in best_parents:
                edges.append({
                    "from_concept_index": c,
                    "to_parent_index": p,
                    "extent_delta_size": best_size_diff,
                })
        return edges

    # ------------------------------------------------------------------
    @staticmethod
    def _to_public(
        c: Dict[str, Any], g_list: List[str], m_list: List[str]
    ) -> Dict[str, Any]:
        ext = [g_list[i] for i in range(len(g_list)) if (c["extent_mask"] >> i) & 1]
        intent = [m_list[j] for j in range(len(m_list)) if (c["intent_mask"] >> j) & 1]
        return {
            "extent": ext,
            "intent": intent,
            "extent_size": len(ext),
            "intent_size": len(intent),
        }
