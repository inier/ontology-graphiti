"""DependencyTracker (T393)

解析表达式依赖，构建 DAG（依赖图）。

实现要点：
- 使用 Python AST 遍历表达式
- 识别 `obj.<property>` 形式的属性访问
- 提取所有依赖属性名（去重、保序）
- 构建 `{property_id: {dependency_ids}}` 字典（正向图）
- 支持反向传播查询 get_downstream(changed_property_id)

简单表达式 vs 复杂表达式：
- 函数调用形式: `func(arg1, arg2)` → 提取 arg1/arg2 中的属性访问
- 嵌套属性: `properties.user.name` → 提取 ['user.name', 'user'] 两层
"""
from __future__ import annotations

import ast
import re
from collections import deque
from typing import Dict, List, Set


class DependencyTracker:
    """表达式依赖追踪器"""

    def __init__(self) -> None:
        self._forward: Dict[str, Set[str]] = {}
        self._reverse: Dict[str, Set[str]] = {}

    # ---------- 公共 API ----------

    def add_property(self, prop_id: str, dependencies: List[str]) -> None:
        """注册一个 ComputedProperty 及其依赖列表"""
        deps = list(dict.fromkeys(dependencies or []))
        if prop_id in self._forward:
            for old_dep in self._forward[prop_id]:
                self._reverse.get(old_dep, set()).discard(prop_id)
        self._forward[prop_id] = set(deps)
        for dep in deps:
            self._reverse.setdefault(dep, set()).add(prop_id)

    def remove_property(self, prop_id: str) -> None:
        """移除一个 ComputedProperty"""
        deps = self._forward.pop(prop_id, set())
        for dep in deps:
            self._reverse.get(dep, set()).discard(prop_id)
        self._reverse.pop(prop_id, None)

    def get_dependencies(self, prop_id: str) -> List[str]:
        """获取某属性的直接依赖列表"""
        return sorted(self._forward.get(prop_id, set()))

    def get_downstream(self, changed_property_id: str) -> List[str]:
        """反向传播：返回依赖 changed_property_id 的所有下游属性（按 BFS 层级排序）"""
        visited: Set[str] = set()
        result: List[str] = []
        queue = deque(self._reverse.get(changed_property_id, set()))
        while queue:
            cur = queue.popleft()
            if cur in visited:
                continue
            visited.add(cur)
            result.append(cur)
            for child in self._reverse.get(cur, set()):
                if child not in visited:
                    queue.append(child)
        return result

    def detect_cycle(self) -> List[str]:
        """检测图中是否存在循环依赖；若有则返回环上的一个节点列表"""
        WHITE, GRAY, BLACK = 0, 1, 2
        color: Dict[str, int] = {n: WHITE for n in self._forward}
        cycle_path: List[str] = []

        def dfs(node: str, path: List[str]) -> bool:
            color[node] = GRAY
            path.append(node)
            for neighbor in self._forward.get(node, set()):
                if neighbor not in color:
                    color[neighbor] = WHITE
                if color[neighbor] == GRAY:
                    if neighbor in path:
                        start = path.index(neighbor)
                        cycle_path.extend(path[start:] + [neighbor])
                    return True
                if color[neighbor] == WHITE:
                    if dfs(neighbor, path):
                        return True
            path.pop()
            color[node] = BLACK
            return False

        for node in list(self._forward.keys()):
            if color[node] == WHITE:
                if dfs(node, []):
                    return cycle_path
        return []

    # ---------- 静态工具 ----------

    @staticmethod
    def extract_from_expression(expression: str) -> List[str]:
        """从表达式中提取依赖属性名（保序去重）"""
        deps: List[str] = []
        seen: Set[str] = set()
        for name in _iter_attr_names(expression):
            if name and name not in seen:
                seen.add(name)
                deps.append(name)
        return deps


# ---------- 内部 AST 遍历工具 ----------


_PROPERTY_TOKEN_RE = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*$")


def _iter_attr_names(expression: str):
    """遍历 AST 节点，yield 所有具名属性访问的末段名称。"""
    try:
        tree = ast.parse(expression, mode="eval")
    except SyntaxError:
        return
    for node in ast.walk(tree):
        if isinstance(node, ast.Attribute):
            name = _attr_last_name(node)
            if name and _PROPERTY_TOKEN_RE.match(name):
                yield name
        elif isinstance(node, ast.Name):
            yield node.id


def _attr_last_name(node: ast.Attribute) -> str:
    """从嵌套属性访问中提取最后一段名字 (a.b.c → 'c')"""
    cur = node
    while isinstance(cur, ast.Attribute):
        cur = cur.value
    return node.attr


__all__ = ["DependencyTracker"]
