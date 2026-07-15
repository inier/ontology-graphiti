"""
ResultMerger — HYBRID 模式下的结果合并器。

接受结构化 rows + 非结构化 rows，按 confidence 排序去重。

合并策略：
1. 同一 id 的结果合并，confidence 取 max
2. 不同 id 的结果按 score 降序
3. 标记 source，便于溯源
"""
import logging
from typing import Any, Dict, List

logger = logging.getLogger(__name__)


def _extract_id(row: Dict[str, Any]) -> str:
    for k in ("id", "object_id", "entity_id"):
        if row.get(k):
            return str(row[k])
    return ""


def _extract_score(row: Dict[str, Any]) -> float:
    for k in ("score", "confidence", "similarity"):
        v = row.get(k)
        if v is not None:
            try:
                return float(v)
            except (TypeError, ValueError):
                return 0.0
    return 0.5


def merge(
    structured_rows: List[Dict[str, Any]],
    unstructured_rows: List[Dict[str, Any]],
    max_size: int = 50,
) -> List[Dict[str, Any]]:
    """合并两类结果，按 score 降序，按 id 去重。"""
    seen: Dict[str, Dict[str, Any]] = {}
    _absorb_structured(seen, structured_rows)
    _absorb_unstructured(seen, unstructured_rows)
    return _sorted_top_n(seen, max_size)


def _absorb_structured(seen: Dict[str, Dict[str, Any]], rows: List[Dict[str, Any]]) -> None:
    for row in rows or []:
        row_id = _extract_id(row)
        merged = dict(row)
        merged["_source"] = "structured"
        merged["_score"] = _extract_score(row)
        if row_id:
            if row_id in seen:
                _maybe_replace(seen[row_id], merged)
            else:
                seen[row_id] = merged
        else:
            seen[f"_anon_{len(seen)}"] = merged


def _absorb_unstructured(seen: Dict[str, Dict[str, Any]], rows: List[Dict[str, Any]]) -> None:
    for row in rows or []:
        row_id = _extract_id(row)
        merged = dict(row)
        merged["_source"] = "unstructured"
        merged["_score"] = _extract_score(row)
        if row_id and row_id in seen:
            existing = seen[row_id]
            if merged["_score"] > existing.get("_score", 0):
                existing["_score"] = merged["_score"]
            existing["_sources"] = list({*(existing.get("_sources", [existing["_source"]])), merged["_source"]})
        else:
            if row_id:
                seen[row_id] = merged
            else:
                seen[f"_anon_{len(seen)}"] = merged


def _maybe_replace(existing: Dict[str, Any], incoming: Dict[str, Any]) -> None:
    if incoming["_score"] > existing.get("_score", 0):
        existing.update(incoming)


def _sorted_top_n(seen: Dict[str, Dict[str, Any]], max_size: int) -> List[Dict[str, Any]]:
    merged_list = list(seen.values())
    merged_list.sort(key=lambda r: r.get("_score", 0.0), reverse=True)
    return merged_list[:max_size]


__all__ = ["merge"]
