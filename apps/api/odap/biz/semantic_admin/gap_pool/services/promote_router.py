"""promote 路由（ADR-090 子项目 D）——按 attribution.layer 决定编辑形态。

风险倒序优先级（D-D2，不倒过来）：schema > tool > content。
  content → candidate_store（现有 USL 候选路径）
  schema  → change_proposal（RFC 6902 JSON Patch）
  tool    → tool_routing（工单）

纯函数模块，不触碰存储/服务；由 gap_service.promote 薄壳调度（D-D8）。
"""
from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Any, Dict, List, Optional

# 风险倒序：结构问题（schema）先于术语（content）解决——根因优先。
LAYER_PRIORITY = ("schema", "tool", "content")
VALID_LAYERS = ("schema", "content", "tool")

ROUTED_TO = {
    "content": "candidate_store",
    "schema": "change_proposal",
    "tool": "tool_routing",
}

DEFAULT_TARGET_KIND = {
    "schema": "object_type",
    "content": "term",
    "tool": "engine",
}


@dataclass(frozen=True)
class RouteResult:
    layer: str
    target_kind: str
    payload: Dict[str, Any]
    routed_to: str


def _counts(gap: Dict[str, Any]) -> Dict[str, int]:
    c = gap.get("attribution_counts_json")
    if isinstance(c, str):
        try:
            c = json.loads(c)
        except (ValueError, TypeError):
            c = {}
    return c if isinstance(c, dict) else {}


def decide_layer(gap: Dict[str, Any]) -> str:
    """无归因 → content（D-D10 旧数据兜底）；否则按风险倒序取计数 >0 的层。"""
    counts = _counts(gap)
    for layer in LAYER_PRIORITY:
        if int(counts.get(layer, 0)) > 0:
            return layer
    return "content"


def attribution_for_layer(gap: Dict[str, Any], layer: str) -> Dict[str, Any]:
    """取最近一条该层归因 occurrence（倒序扫描）。无 → {}。"""
    for occ in reversed(gap.get("sources_json") or []):
        attr = occ.get("attribution") or {}
        if attr.get("layer") == layer:
            return attr
    return {}


def target_kind_for(gap: Dict[str, Any], layer: str) -> str:
    attr = attribution_for_layer(gap, layer)
    return str(attr.get("target_kind") or DEFAULT_TARGET_KIND.get(layer, "term"))


def build_schema_patch(gap: Dict[str, Any], target_kind: str) -> List[Dict[str, Any]]:
    """按 target_kind 产 RFC 6902 ops；无法判定 → 空 list（不造数）。"""
    expr = gap.get("expression")
    if not expr:
        return []
    if target_kind == "object_type":
        return [{"op": "add", "path": f"/object_types/{expr}",
                 "value": {"name": expr}}]
    if target_kind == "relation_type":
        return [{"op": "add", "path": f"/relation_types/{expr}",
                 "value": {"name": expr}}]
    if target_kind == "property":
        attr = attribution_for_layer(gap, "schema")
        parent = attr.get("parent") or attr.get("target_ref") or "Unknown"
        return [{"op": "add",
                 "path": f"/object_types/{parent}/properties/{expr}",
                 "value": {"name": expr}}]
    return []


def route(gap: Dict[str, Any], force_layer: Optional[str] = None) -> RouteResult:
    """决定 layer + target_kind + payload + routed_to。"""
    layer = force_layer if force_layer in VALID_LAYERS else decide_layer(gap)
    target_kind = target_kind_for(gap, layer)
    payload: Dict[str, Any] = {
        "expression": gap.get("expression"),
        "gap_id": gap.get("id"),
        "scope_key": gap.get("scope_key"),
        "workspace_id": gap.get("workspace_id"),
        "domain_id": gap.get("domain_id"),
        "target_kind": target_kind,
    }
    if layer == "schema":
        payload["changes"] = build_schema_patch(gap, target_kind)
    if layer == "tool":
        attr = attribution_for_layer(gap, "tool")
        payload["engine"] = attr.get("target_ref") or "unknown_engine"
    return RouteResult(layer=layer, target_kind=target_kind,
                       payload=payload, routed_to=ROUTED_TO[layer])


__all__ = [
    "RouteResult", "route", "decide_layer", "target_kind_for",
    "build_schema_patch", "attribution_for_layer",
    "LAYER_PRIORITY", "VALID_LAYERS", "ROUTED_TO",
]
