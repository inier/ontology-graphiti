"""scanners —— 漂移扫描纯函数（无 LLM、无推断、无副作用）。"""
from __future__ import annotations

from typing import Any, Dict, List

from ..models.drift import DriftKind, EvolutionSource


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


_ENTITY_FIELDS = ("name", "name_en", "aliases", "basic_properties",
                  "statistical_properties", "capabilities", "constraints")
_RELATION_FIELDS = ("source_entity", "target_entity", "relation_type", "properties")
_RULE_FIELDS = ("condition", "consequence", "priority")
_CONSTRAINT_FIELDS = ("constraint_type", "description", "scope",
                      "violation_consequence", "legal_basis")
_TERM_FIELDS = ("canonical", "synonyms", "near_synonyms", "aliases",
                "definition", "semantic_type", "stoplist_flag")


def _index_by(items, key):
    out = {}
    for it in (items or []):
        k = it.get(key)
        if k is not None:
            out[k] = it
    return out


def _diff_bodies(idx_a, idx_b, fields, *, kind_source, version_ref, label_fn):
    """通用字段级 diff：返回 finding dict 列表（新增/删除/字段变更）。"""
    findings = []
    for k, b in idx_b.items():
        if k not in idx_a:
            findings.append({
                "kind": DriftKind.EVOLUTION.value, "source": kind_source,
                "subject": str(k), "subject_label": label_fn(b),
                "field": "__added__", "old_value_json": None, "new_value_json": b,
                "version_ref_json": version_ref,
            })
            continue
        a = idx_a[k]
        for fld in fields:
            av, bv = a.get(fld), b.get(fld)
            if av != bv:
                findings.append({
                    "kind": DriftKind.EVOLUTION.value, "source": kind_source,
                    "subject": str(k), "subject_label": label_fn(b),
                    "field": fld, "old_value_json": av, "new_value_json": bv,
                    "version_ref_json": version_ref,
                })
    for k, a in idx_a.items():
        if k not in idx_b:
            findings.append({
                "kind": DriftKind.EVOLUTION.value, "source": kind_source,
                "subject": str(k), "subject_label": label_fn(a),
                "field": "__removed__", "old_value_json": a, "new_value_json": None,
                "version_ref_json": version_ref,
            })
    return findings


def diff_version_snapshots(snap_a: Dict[str, Any], snap_b: Dict[str, Any], *,
                           version_a: str, version_b: str) -> List[Dict[str, Any]]:
    """相邻版本 doc_snapshot 字段级 diff（entities/relations/rules/constraints）。

    actions/events 为运行时数据，明示不进 diff。
    """
    vref = {"version_a": version_a, "version_b": version_b}
    src = EvolutionSource.VERSION_SNAPSHOT.value
    out: List[Dict[str, Any]] = []
    out += _diff_bodies(_index_by(snap_a.get("entities"), "entity_id"),
                        _index_by(snap_b.get("entities"), "entity_id"),
                        _ENTITY_FIELDS, kind_source=src, version_ref=vref,
                        label_fn=lambda x: x.get("name") or x.get("entity_id"))
    out += _diff_bodies(_index_by(snap_a.get("relations"), "relation_id"),
                        _index_by(snap_b.get("relations"), "relation_id"),
                        _RELATION_FIELDS, kind_source=src, version_ref=vref,
                        label_fn=lambda x: x.get("relation_id"))
    out += _diff_bodies(_index_by(snap_a.get("rules"), "rule_id"),
                        _index_by(snap_b.get("rules"), "rule_id"),
                        _RULE_FIELDS, kind_source=src, version_ref=vref,
                        label_fn=lambda x: x.get("description") or x.get("rule_id"))
    out += _diff_bodies(_index_by(snap_a.get("constraints"), "constraint_id"),
                        _index_by(snap_b.get("constraints"), "constraint_id"),
                        _CONSTRAINT_FIELDS, kind_source=src, version_ref=vref,
                        label_fn=lambda x: x.get("description") or x.get("constraint_id"))
    return out


def diff_indicator_snapshots(rows: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """indicator 口径快照按 captured_at 序相邻 diff definition_json 键级。"""
    src = EvolutionSource.INDICATOR_CALIBER.value
    ordered = sorted(rows or [], key=lambda r: r.get("captured_at") or "")
    out: List[Dict[str, Any]] = []
    for prev, cur in zip(ordered, ordered[1:]):
        vref = {"prev_at": prev.get("captured_at"), "cur_at": cur.get("captured_at")}
        pid = cur.get("indicator_id") or prev.get("indicator_id")
        pdef, cdef = prev.get("definition_json") or {}, cur.get("definition_json") or {}
        op = cur.get("change_op", "update")
        if op == "delete":
            out.append({"kind": DriftKind.EVOLUTION.value, "source": src,
                        "subject": str(pid), "subject_label": str(pid),
                        "field": "__removed__", "old_value_json": pdef,
                        "new_value_json": None, "version_ref_json": vref})
            continue
        if prev.get("change_op") == "create" and op == "create":
            continue
        for fld in sorted(set(pdef) | set(cdef)):
            if pdef.get(fld) != cdef.get(fld):
                out.append({"kind": DriftKind.EVOLUTION.value, "source": src,
                            "subject": str(pid), "subject_label": str(pid),
                            "field": fld, "old_value_json": pdef.get(fld),
                            "new_value_json": cdef.get(fld), "version_ref_json": vref})
    return out


def diff_term_history(rows: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """USL 术语历史按 at 序相邻 diff before/after 的关键字段。"""
    src = EvolutionSource.USL_TERM.value
    ordered = sorted(rows or [], key=lambda r: r.get("at") or "")
    out: List[Dict[str, Any]] = []
    for prev, cur in zip(ordered, ordered[1:]):
        vref = {"prev_at": prev.get("at"), "cur_at": cur.get("at")}
        tid = cur.get("term_id") or prev.get("term_id")
        before = cur.get("before_json") or prev.get("after_json") or {}
        after = cur.get("after_json") or {}
        if cur.get("op") == "delete":
            out.append({"kind": DriftKind.EVOLUTION.value, "source": src,
                        "subject": str(tid), "subject_label": str(before.get("canonical") or tid),
                        "field": "__removed__", "old_value_json": before,
                        "new_value_json": None, "version_ref_json": vref})
            continue
        for fld in _TERM_FIELDS:
            if before.get(fld) != after.get(fld):
                out.append({"kind": DriftKind.EVOLUTION.value, "source": src,
                            "subject": str(tid),
                            "subject_label": str(after.get("canonical") or tid),
                            "field": fld, "old_value_json": before.get(fld),
                            "new_value_json": after.get(fld), "version_ref_json": vref})
    return out
