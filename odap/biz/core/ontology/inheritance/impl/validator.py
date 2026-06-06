"""
InheritanceValidator 实现 (T367)

检测：
1. 循环继承（迭代 DFS，避免栈溢出）
2. 最大深度限制（5 层）
3. Mixin 冲突（Mixin 提供的属性与父类属性重名）
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, List, Set, Tuple

from ..models.inheritance import InheritanceEdge
from ..models.mixin import Mixin


# 继承最大深度（5 层）
MAX_INHERITANCE_DEPTH = 5


@dataclass
class ValidationResult:
    """验证结果"""
    is_valid: bool
    errors: List[str] = field(default_factory=list)
    warnings: List[str] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "is_valid": self.is_valid,
            "errors": list(self.errors),
            "warnings": list(self.warnings),
        }


def _build_graph(edges: List[InheritanceEdge]) -> Dict[str, List[str]]:
    """构建 child → [parent, ...] 邻接表"""
    graph: Dict[str, List[str]] = {}
    for edge in edges:
        graph.setdefault(edge.child_type_id, []).append(edge.parent_type_id)
    return graph


def _detect_cycle_iterative(graph: Dict[str, List[str]]) -> List[str]:
    """
    迭代 DFS 检测有向图中的环。
    返回环路节点序列（首尾相接）；若无环返回空列表。
    """
    WHITE, GRAY, BLACK = 0, 1, 2
    color: Dict[str, int] = {n: WHITE for n in graph}
    parent: Dict[str, str] = {}

    for start in graph:
        if color[start] != WHITE:
            continue
        # 迭代 DFS：栈中保存 (node, iterator_over_children)
        stack: List[Tuple[str, Any]] = [(start, iter(graph.get(start, [])))]
        color[start] = GRAY
        while stack:
            node, it = stack[-1]
            nxt = next(it, None)
            if nxt is None:
                color[node] = BLACK
                stack.pop()
                continue
            if nxt not in color:
                color[nxt] = WHITE
            if color[nxt] == GRAY:
                # 找到回边 → 还原环
                cycle = [nxt, node]
                cur = node
                while cur in parent and parent[cur] != nxt:
                    cur = parent[cur]
                    cycle.append(cur)
                cycle.append(nxt)
                cycle.reverse()
                return cycle
            if color[nxt] == WHITE:
                color[nxt] = GRAY
                parent[nxt] = node
                stack.append((nxt, iter(graph.get(nxt, []))))
    return []


def _compute_depths(edges: List[InheritanceEdge]) -> Dict[str, int]:
    """
    简单计算每个 child_type_id 的入度（=直接父类数量）。
    这里 depth 取最大父类深度 + 1；若循环则返回 -1。
    """
    graph = _build_graph(edges)
    cycle = _detect_cycle_iterative(graph)
    if cycle:
        return {"_cycle": cycle}
    depth: Dict[str, int] = {}

    def dfs(node: str, visiting: Set[str]) -> int:
        if node in depth:
            return depth[node]
        if node in visiting:
            return 0
        visiting.add(node)
        max_parent_depth = 0
        for parent in graph.get(node, []):
            max_parent_depth = max(max_parent_depth, dfs(parent, visiting) + 1)
        visiting.discard(node)
        depth[node] = max_parent_depth
        return max_parent_depth

    for node in graph:
        dfs(node, set())
    return depth


def validate_inheritance_chain(edges: List[InheritanceEdge]) -> ValidationResult:
    """
    验证继承链：
    1. 检测循环
    2. 检测最大深度
    """
    errors: List[str] = []
    warnings: List[str] = []

    graph = _build_graph(edges)
    cycle = _detect_cycle_iterative(graph)
    if cycle:
        cycle_str = " -> ".join(cycle)
        errors.append(f"Cycle detected in inheritance graph: {cycle_str}")

    depths = _compute_depths(edges)
    for node, d in depths.items():
        if node == "_cycle":
            continue
        if d > MAX_INHERITANCE_DEPTH:
            errors.append(
                f"Inheritance depth {d} for type '{node}' exceeds "
                f"maximum {MAX_INHERITANCE_DEPTH}"
            )
        elif d == MAX_INHERITANCE_DEPTH:
            warnings.append(
                f"Inheritance depth for type '{node}' reached limit "
                f"{MAX_INHERITANCE_DEPTH}"
            )

    return ValidationResult(
        is_valid=len(errors) == 0,
        errors=errors,
        warnings=warnings,
    )


def validate_mixin_conflicts(
    type_id: str,
    mixins: List[Mixin],
    type_properties: List[str],
    parent_property_names: List[str] = None,
) -> ValidationResult:
    """
    验证 Mixin 是否与 ObjectType 自身 / 父类属性冲突。
    """
    errors: List[str] = []
    warnings: List[str] = []
    owned = set(type_properties or [])
    parents = set(parent_property_names or [])

    for mixin in mixins:
        for prop in mixin.properties:
            if prop in owned:
                warnings.append(
                    f"Mixin '{mixin.name}' property '{prop}' shadows "
                    f"own property of type '{type_id}'"
                )
            if prop in parents:
                warnings.append(
                    f"Mixin '{mixin.name}' property '{prop}' conflicts with "
                    f"parent property of type '{type_id}'"
                )

    return ValidationResult(
        is_valid=len(errors) == 0,
        errors=errors,
        warnings=warnings,
    )


class InheritanceValidator:
    """继承验证器（OO 接口形式）"""

    def validate_chain(self, edges: List[InheritanceEdge]) -> ValidationResult:
        return validate_inheritance_chain(edges)

    def validate_mixins(
        self,
        type_id: str,
        mixins: List[Mixin],
        type_properties: List[str],
        parent_property_names: List[str] = None,
    ) -> ValidationResult:
        return validate_mixin_conflicts(
            type_id, mixins, type_properties, parent_property_names
        )
