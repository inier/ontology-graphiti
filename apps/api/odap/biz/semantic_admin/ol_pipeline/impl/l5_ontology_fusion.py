"""L5 Ontology Fusion — 候选术语 vs 现有 USL 三分类决策。

Approach (纯逻辑，零依赖)：
  对每个候选，与 USL 中同 semantic_type 的 N 个最近邻做相似度评估
  = w1*jaccard(tokens) + w2*(1 - normalized_edit) + w3*synonym_overlap + w4*semantic_type_match

  决策阈值：
    score ≥ 0.82  → "merge"（与现有术语高度相似，合并属性，保留现有 canonical）
    0.45 ≤ score < 0.82 → "flag_conflict"（可能是同一概念但存疑，推 HITL 人工审查）
    score < 0.45 → "keep_as_new"（新术语入库）

  Constraint：候选 semantic_type != 已有 semantic_type 时
    如果相似度 ≥ 0.9，仍强制 flag_conflict（跨类型冲突，需人工确认）
    否则直接 keep_as_new（防止跨类型误 merge）
"""

from __future__ import annotations

import re
from difflib import SequenceMatcher
from typing import Any, Dict, Iterable, List, Optional, Tuple

TOKEN_RE = re.compile(r"[\u4e00-\u9fffA-Za-z0-9_]+")
DEFAULT_WEIGHTS = (0.35, 0.30, 0.20, 0.15)
DEFAULT_THRESHOLDS = (0.82, 0.45)  # (merge ≥ t1, flag_conflict ≥ t2, else keep)


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------
class OntologyFusionService:
    """USL 本体融合器：新候选 与 现有 USL 术语集 做两两匹配 → 三分类决策。"""

    def __init__(
        self,
        *,
        weights: Tuple[float, float, float, float] = DEFAULT_WEIGHTS,
        thresholds: Tuple[float, float] = DEFAULT_THRESHOLDS,
        top_k_neighbors: int = 3,
    ) -> None:
        w = tuple(float(x) for x in weights)
        s = sum(w) or 1.0
        self.weights: Tuple[float, float, float, float] = tuple(x / s for x in w)  # 归一化
        self.merge_threshold, self.flag_threshold = (
            float(thresholds[0]),
            float(thresholds[1]),
        )
        self.top_k_neighbors = max(1, int(top_k_neighbors or 1))

    # ------------------------------------------------------------------
    def fuse_candidates(
        self,
        *,
        new_candidates: Iterable[Dict[str, Any]],
        existing_terms: Iterable[Dict[str, Any]],
    ) -> List[Dict[str, Any]]:
        """把每个候选与 existing_terms 比，返回决策列表。

        Args:
            new_candidates: [{canonical, synonyms?, semantic_type?, definition?, aliases?, ...}]
            existing_terms: 同 shape（USL 已有术语）

        Returns:
            List length == len(new_candidates)：
              [{
                "candidate_canonical": str,
                "decision": "merge" | "keep_as_new" | "flag_conflict",
                "decision_score": float,  # 0~1
                "best_match": {term_canonical, similarity, match_reason} | None,
                "top_matches": [...],  # top-K
                "merge_field_suggestion": Dict | None,  # merge 时建议合并字段
              }, ...]
        """
        existing: List[Dict[str, Any]] = [
            t for t in (existing_terms or []) if (t or {}).get("canonical")
        ]
        # 注：为避免分桶漏了"同名但不同类型"的场景，直接全量 pairwise。
        # 对术语数 ≤10,000 规模、候选数 ≤ 几百场景完全够用；
        # 需要更大规模时可加倒排索引。
        decisions: List[Dict[str, Any]] = []
        for cand in new_candidates or []:
            cand_canon = str((cand or {}).get("canonical") or "").strip()
            if not cand_canon:
                decisions.append({
                    "candidate_canonical": "",
                    "decision": "keep_as_new",
                    "decision_score": 0.0,
                    "best_match": None,
                    "top_matches": [],
                    "merge_field_suggestion": None,
                })
                continue
            cand_st = str(cand.get("semantic_type") or "").strip() or "any"
            # 相似度
            scored: List[Tuple[float, Dict[str, Any], Dict[str, Any]]] = []
            for t in existing:
                sim, reason = self.pairwise_similarity(cand, t)
                scored.append((sim, t, reason))
            scored.sort(key=lambda x: -x[0])
            top_k = scored[: self.top_k_neighbors]
            best_sim, best_term, best_reason = scored[0] if scored else (0.0, None, {})
            # 决策
            decision, decision_score, cross_type_override = self._decide(
                cand_st,
                str((best_term or {}).get("semantic_type") or "").strip() or "any",
                best_sim,
            )
            if cross_type_override:
                best_reason = dict(best_reason or {})
                best_reason["cross_type_override"] = True
            best_match_info: Optional[Dict[str, Any]] = None
            merge_suggestion: Optional[Dict[str, Any]] = None
            if best_term:
                best_match_info = {
                    "term_canonical": best_term.get("canonical"),
                    "similarity": round(best_sim, 3),
                    "match_reason": best_reason,
                }
                if decision == "merge":
                    merge_suggestion = self._build_merge_fields(cand, best_term)
            top_matches_info = [
                {
                    "term_canonical": t.get("canonical"),
                    "similarity": round(s, 3),
                    "match_reason": r,
                }
                for s, t, r in top_k
            ]
            decisions.append({
                "candidate_canonical": cand_canon,
                "decision": decision,
                "decision_score": round(decision_score, 3),
                "best_match": best_match_info,
                "top_matches": top_matches_info,
                "merge_field_suggestion": merge_suggestion,
            })
        return decisions

    # ------------------------------------------------------------------
    def pairwise_similarity(
        self, a: Dict[str, Any], b: Dict[str, Any]
    ) -> Tuple[float, Dict[str, Any]]:
        """候选 vs 单个已有术语的加权综合相似度 + 分维明细。

        Returns:
            (score 0~1, detail_dict{dimension_scores, weights_used})
        """
        w = self.weights
        # dim 1: Jaccard(token set)
        a_tokens = self._tokens(a)
        b_tokens = self._tokens(b)
        j = self._jaccard(a_tokens, b_tokens)
        # dim 2: 1 - normalized edit distance (canonical vs canonical + synonyms max)
        edit_sim = self._max_edit_similarity(
            self._all_names(a), self._all_names(b)
        )
        # dim 3: synonym overlap（除 canonical 外的同义词）
        a_syn = self._synonym_set(a)
        b_syn = self._synonym_set(b)
        syn_overlap = 0.0
        if a_syn or b_syn:
            inter = len(a_syn & b_syn)
            union = len(a_syn | b_syn)
            syn_overlap = inter / union if union else 1.0 if (not a_syn and not b_syn) else 0.0
        # dim 4: semantic_type match
        a_st = str(a.get("semantic_type") or "").strip()
        b_st = str(b.get("semantic_type") or "").strip()
        type_match = 1.0 if (a_st and a_st == b_st) else 0.0
        score = float(
            w[0] * j + w[1] * edit_sim + w[2] * syn_overlap + w[3] * type_match
        )
        # Exact canonical match boost: 同名 + 同类型 绝对高置信 merge
        a_canon = str(a.get("canonical") or "").strip().lower()
        b_canon = str(b.get("canonical") or "").strip().lower()
        exact_name = bool(a_canon and a_canon == b_canon)
        if exact_name and type_match:
            score = max(score, 0.98)
        elif exact_name:
            # 同名但不同类型：也给高 boost，但不能直接 merge，会被 _decide 的跨类型规则压到 flag
            score = max(score, 0.92)
        detail = {
            "dimension_scores": {
                "jaccard": round(j, 3),
                "edit_similarity": round(edit_sim, 3),
                "synonym_overlap": round(syn_overlap, 3),
                "semantic_type_match": type_match,
            },
            "weights_used": {
                "w_jaccard": round(w[0], 3),
                "w_edit": round(w[1], 3),
                "w_syn": round(w[2], 3),
                "w_type": round(w[3], 3),
            },
            "exact_canonical_match": exact_name,
        }
        return min(1.0, max(0.0, score)), detail

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------
    def _decide(
        self,
        cand_st: str,
        exist_st: str,
        best_sim: float,
    ) -> Tuple[str, float, bool]:
        """返回 (decision, score, cross_type_override)。"""
        cross_type = bool(cand_st and exist_st and cand_st != exist_st)
        score = float(best_sim)
        if not cross_type:
            if score >= self.merge_threshold:
                return "merge", score, False
            if score >= self.flag_threshold:
                return "flag_conflict", score, False
            return "keep_as_new", score, False
        # 跨类型：即使很高分，也最多 flag_conflict，不能 merge
        if score >= 0.90:
            return "flag_conflict", score, True
        if score >= self.flag_threshold:
            return "flag_conflict", score, True
        return "keep_as_new", score, False

    # ------------------------------------------------------------------
    @staticmethod
    def _tokens(x: Dict[str, Any]) -> set:
        parts: List[str] = []
        for key in ("canonical", "definition", "description"):
            v = x.get(key)
            if isinstance(v, str):
                parts.extend(TOKEN_RE.findall(v.lower()))
        if parts:
            return set(parts)
        return set()

    @staticmethod
    def _all_names(x: Dict[str, Any]) -> List[str]:
        out: List[str] = []
        seen: set = set()
        canon = str(x.get("canonical") or "").strip()
        if canon:
            out.append(canon)
            seen.add(canon)
        for field in ("synonyms", "aliases", "near_synonyms", "acronyms"):
            v = x.get(field)
            if isinstance(v, (list, tuple, set)):
                for s in v:
                    ss = str(s or "").strip()
                    if ss and ss not in seen:
                        out.append(ss)
                        seen.add(ss)
        return out

    @staticmethod
    def _synonym_set(x: Dict[str, Any]) -> set:
        out: set = set()
        canon = str(x.get("canonical") or "").strip()
        for field in ("synonyms", "aliases", "near_synonyms", "acronyms"):
            v = x.get(field)
            if isinstance(v, (list, tuple, set)):
                for s in v:
                    ss = str(s or "").strip()
                    if ss and ss != canon:
                        out.add(ss.lower())
        return out

    @staticmethod
    def _jaccard(a: set, b: set) -> float:
        if not a and not b:
            return 1.0
        if not a or not b:
            return 0.0
        inter = len(a & b)
        union = len(a | b)
        return inter / union if union else 0.0

    @staticmethod
    def _max_edit_similarity(names_a: List[str], names_b: List[str]) -> float:
        if not names_a or not names_b:
            return 0.0
        best = 0.0
        for a in names_a:
            for b in names_b:
                sim = SequenceMatcher(None, a.lower(), b.lower()).ratio()
                if sim > best:
                    best = sim
        return float(best)

    # ------------------------------------------------------------------
    @staticmethod
    def _build_merge_fields(
        cand: Dict[str, Any], exist: Dict[str, Any]
    ) -> Dict[str, Any]:
        """建议合并字段（简单启发式：列表取并集，文本取更长，其他保留 exist）。"""
        merged: Dict[str, Any] = {}
        # 列表字段取并集（去重保序）
        list_fields = ("synonyms", "aliases", "near_synonyms", "examples", "acronyms", "tags")
        for fld in list_fields:
            combined: List[Any] = []
            seen_any: set = set()
            for src in (exist, cand):
                lst = src.get(fld) or []
                if not isinstance(lst, (list, tuple, set)):
                    continue
                for item in lst:
                    key = str(item).lower()
                    if key in seen_any:
                        continue
                    seen_any.add(key)
                    combined.append(item)
            if combined:
                merged[fld] = combined
        # 长文本字段取更长且非空者
        text_fields = ("definition", "description")
        for fld in text_fields:
            ev = exist.get(fld) or ""
            cv = cand.get(fld) or ""
            if len(str(cv)) > len(str(ev)):
                merged[fld] = cv
            elif ev:
                merged[fld] = ev
        # confidence: 取 max
        try:
            merged["confidence"] = max(
                float(exist.get("confidence") or 0.0),
                float(cand.get("confidence") or 0.0),
            )
        except Exception:
            pass
        return merged
