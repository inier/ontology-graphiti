"""SHACL 合规率计算与 provider 工厂（ADR-084 F7 落地）。

职责边界：
1. ``compliance_ratio(shapes, data)`` —— 纯函数，用 pyshacl 计算 [0,1] 合规率；
2. ``make_storage_provider(...)`` —— 从 shacl_store 读形状 + 注入的图构造器，
   产出 ``QualityCalculator(shacl_provider=...)`` 可调用的 provider。

缺值语义（AGENTS.md 规则 14）：
- 无形状、无实例图、无法确定目标节点集合 → 返回 ``None``；
- 由 ``QualityCalculator`` 标记 ``evaluated=False``，**禁止在此回退满分**。
"""

from __future__ import annotations

import logging
from typing import Any, Callable, Dict, Iterable, Optional

logger = logging.getLogger(__name__)

_SH = "http://www.w3.org/ns/shacl#"
_RDF_TYPE = "http://www.w3.org/1999/02/22-rdf-syntax-ns#type"

def _as_graph(value: Any) -> Any:
    """把 str/bytes/rdflib.Graph 统一成 rdflib.Graph；无法解析返回 None。"""
    if value is None:
        return None
    try:
        from rdflib import Graph
    except ImportError as exc:  # pragma: no cover - 依赖缺失必须显式失败
        raise RuntimeError("rdflib 未安装，无法计算 SHACL 合规率") from exc

    if isinstance(value, Graph):
        return value
    graph = Graph()
    try:
        if isinstance(value, bytes):
            graph.parse(data=value.decode("utf-8"), format="turtle")
        elif isinstance(value, str):
            graph.parse(data=value, format="turtle")
        else:
            return None
    except Exception as exc:
        logger.error("SHACL 图解析失败: %s", exc)
        return None
    return graph


def compliance_ratio(shapes: Any, data: Any) -> Optional[float]:
    """计算 SHACL 合规率 = 1 - (违规 focus node 数 / 目标 focus node 总数)。

    Args:
        shapes: SHACL 形状图（Turtle 字符串 / bytes / rdflib.Graph）
        data:   实例数据图（同上）

    Returns:
        [0,1] 合规率；无法评估（解析失败 / 无 targetClass / 无目标实例）→ None。
    """
    try:
        import pyshacl
    except ImportError as exc:  # pragma: no cover
        raise RuntimeError("pyshacl 未安装，无法计算 SHACL 合规率") from exc

    shapes_graph = _as_graph(shapes)
    data_graph = _as_graph(data)
    if shapes_graph is None or data_graph is None:
        return None

    from rdflib import URIRef

    target_class_pred = URIRef(_SH + "targetClass")
    rdf_type_pred = URIRef(_RDF_TYPE)
    focus_node_pred = URIRef(_SH + "focusNode")

    target_classes = set(shapes_graph.objects(None, target_class_pred))
    if not target_classes:
        # targetNode / SPARQL target 无法从图上反推分母，无法给出"率"
        return None

    focus_total = set()
    for cls in target_classes:
        focus_total |= set(data_graph.subjects(rdf_type_pred, cls))
    if not focus_total:
        return None

    conforms, results_graph, _ = pyshacl.validate(
        data_graph,
        shacl_graph=shapes_graph,
        inference="rdfs",
        abort_on_first=False,
    )
    if conforms:
        return 1.0

    violating = set(results_graph.objects(None, focus_node_pred))
    hit = violating & focus_total
    return max(0.0, 1.0 - len(hit) / len(focus_total))


def make_storage_provider(
    storage: Any,
    *,
    workspace_id: str,
    ontology_version_id: Optional[str],
    graph_builder: Callable[[Dict[str, Any]], Any],
    page_size: int = 50,
) -> Callable[[Dict[str, Any]], Optional[float]]:
    """构造 ``QualityCalculator`` 可用的 SHACL provider。

    Args:
        storage: ``SQLiteShaclStorage`` 实例（需提供 list_shapes）
        workspace_id: 工作空间隔离键（必填，禁止跨租户读形状）
        ontology_version_id: 可选，限定本体版本
        graph_builder: candidate → 实例数据图（Turtle/Graph）；返回 None 表示无法构造
        page_size: 形状分页大小

    Returns:
        provider(candidate) -> Optional[float]
    """
    if not workspace_id:
        raise ValueError("workspace_id 为必填，SHACL 形状读取必须按工作空间隔离")

    def provider(candidate: Dict[str, Any]) -> Optional[float]:
        shapes, _total = storage.list_shapes(
            workspace_id=workspace_id,
            ontology_version_id=ontology_version_id,
            page_size=page_size,
        )
        ttl_parts: Iterable[str] = [
            str(s.get("shape_ttl") or "") for s in (shapes or [])
        ]
        shapes_ttl = "\n".join(p for p in ttl_parts if p.strip()).strip()
        if not shapes_ttl:
            return None

        data = graph_builder(candidate)
        if data is None:
            return None

        return compliance_ratio(shapes_ttl, data)

    return provider


__all__ = ["compliance_ratio", "make_storage_provider"]
