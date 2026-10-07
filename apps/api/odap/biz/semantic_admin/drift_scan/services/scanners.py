"""scanners —— 漂移扫描纯函数（无 LLM、无推断、无副作用）。"""
from __future__ import annotations

from typing import Any, Dict, List

from ..models.drift import DriftKind


def _expressions_of(term: Dict[str, Any]) -> List[str]:
    """展开一个术语的全部说法原文（canonical + synonyms + near_synonyms + aliases）。"""
    out: List[str] = []
    canonical = str(term.get("canonical") or "").strip()
    if canonical:
        out.append(canonical)
    for key in ("synonyms", "near_synonyms", "aliases"):
        for e in (term.get(key) or []):
            es = str(e).strip()
            if es:
                out.append(es)
    return out


def fork_scan(terms: List[Dict[str, Any]], scope: Dict[str, Any]) -> List[Dict[str, Any]]:
    """术语分叉扫描：同一说法原文挂到 ≥2 个 distinct term 即分叉。

    排除 stoplist_flag=True 的术语与空串/纯空白表达。
    返回 finding dict 列表（不含 report_id，由 service 补）。
    """
    expr_map: Dict[str, List[Dict[str, Any]]] = {}
    for t in terms:
        if t.get("stoplist_flag"):
            continue
        side = {
            "term_id": t.get("id"), "canonical": t.get("canonical"),
            "domain_id": t.get("domain_id"), "semantic_type": str(t.get("semantic_type") or ""),
            "from_list": [],
        }
        for expr in _expressions_of(t):
            entry = expr_map.setdefault(expr, [])
            # 记录该 side 从哪个列表命中（证据可追溯）
            hit_from = "canonical" if expr == str(t.get("canonical") or "").strip() else "synonym"
            side_copy = dict(side)
            side_copy["from_list"] = [hit_from]
            entry.append(side_copy)

    findings: List[Dict[str, Any]] = []
    for expr, sides in expr_map.items():
        distinct = {s["term_id"] for s in sides if s.get("term_id")}
        if len(distinct) >= 2:
            # 每个 term 合并成一侧（去重 term_id）
            merged: Dict[str, Dict[str, Any]] = {}
            for s in sides:
                tid = s.get("term_id")
                if tid is None:
                    continue
                if tid not in merged:
                    merged[tid] = dict(s)
                else:
                    merged[tid]["from_list"] = sorted(
                        set(merged[tid]["from_list"]) | set(s["from_list"]))
            findings.append({
                "kind": DriftKind.FORK.value, "source": "", "subject": expr,
                "subject_label": expr, "sides_json": list(merged.values()),
            })
    findings.sort(key=lambda f: f["subject"])
    return findings
