"""MetricDefinitionService — 加载 MetricDefinition + 按 bindings/formula 计算 (T024).

计算流程：
1. resolve_and_compute(name): storage.get_by_name() 加载定义；无定义返回 None
   （供 MetricEngine 在无自定义指标时 fallback 到 TBox 自动派生）
2. compute(definition): 对每个 MetricBinding：
   - 构造 DSL `.entity type:{source_entity_type_id}` + filter_condition
   - 调 QueryService.execute_async 取 rows
   - 提取 source_property_id 列做 aggregation
3. formula 非空：AST 白名单安全求值（仅 BinOp/UnaryOp/Constant/Name + 算术运算符）
4. formula 为空：返回首 binding 聚合值
5. formula 危险或失败：降级返回首 binding 聚合值（不执行危险调用）

安全：禁止 Call/Attribute/Import/Subscript 等节点（白名单严格）。
空集：AVG/RATIO 返回 0（不除零）。
Enum 兼容：aggregation 可为 AggregationFunction 或 .value 字符串。

Constitution I: 函数体 ≤ 40 行。
Constitution IV: 不新建接口；仅一个实现类。
"""

from __future__ import annotations

import ast
import logging
import operator
from typing import Any, Dict, List, Optional

logger = logging.getLogger("semantic_retrieval.metric_definition_service")

# 安全的二元/一元运算符
_BIN_OPS = {
    ast.Add: operator.add,
    ast.Sub: operator.sub,
    ast.Mult: operator.mul,
    ast.Div: operator.truediv,
    ast.Mod: operator.mod,
    ast.Pow: operator.pow,
    ast.FloorDiv: operator.floordiv,
}

_UNARY_OPS = {ast.USub: operator.neg, ast.UAdd: operator.pos}


class MetricDefinitionService:
    """加载 MetricDefinition 并按 bindings + formula 计算 (T024)。"""

    def __init__(self, query_service: Any, storage: Any) -> None:
        self._qs = query_service
        self._storage = storage

    async def resolve_and_compute(
        self, workspace_id: str, metric_name: str
    ) -> Optional[Dict[str, Any]]:
        """按名加载并计算；无定义返回 None（供 MetricEngine fallback TBox）。"""
        d = self._storage.get_by_name(metric_name)
        if d is None:
            return None
        return await self.compute(workspace_id, d)

    async def compute(
        self, workspace_id: str, definition: Any
    ) -> Optional[Dict[str, Any]]:
        """按 MetricDefinition 计算（dict 或 MetricDefinition 对象）。"""
        d = self._coerce_dict(definition)
        bindings = d.get("bindings", [])
        if not bindings:
            return None
        values = await self._eval_bindings(workspace_id, bindings)
        value = self._compute_value(d, values)
        return self._build_result(d, values, value)

    # ------------------------------------------------------------------
    # helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _coerce_dict(definition: Any) -> Dict[str, Any]:
        if isinstance(definition, dict):
            return definition
        if hasattr(definition, "model_dump"):
            return definition.model_dump(mode="json")
        raise TypeError(f"unsupported definition type: {type(definition)}")

    async def _eval_bindings(
        self, workspace_id: str, bindings: List[Dict[str, Any]]
    ) -> Dict[str, float]:
        """对每个 binding 执行查询并聚合；返回 {alias: value}。"""
        out: Dict[str, float] = {}
        for b in bindings:
            rows = await self._fetch_rows(workspace_id, b)
            alias = b.get("alias") or b.get("source_property_id", "")
            out[alias] = self._aggregate(rows, b)
        return out

    async def _fetch_rows(
        self, workspace_id: str, binding: Dict[str, Any]
    ) -> List[Dict[str, Any]]:
        """按 binding 构造 DSL `.entity type:X [filter]` 取 rows。"""
        etype = binding.get("source_entity_type_id", "")
        dsl = f".entity type:{etype}"
        filt = binding.get("filter_condition")
        if filt:
            dsl = f"{dsl} {filt}"
        raw = await self._qs.execute_async(workspace_id, dsl, limit=1000)
        return self._extract_rows(raw)

    @staticmethod
    def _extract_rows(raw: Any) -> List[Dict[str, Any]]:
        if hasattr(raw, "rows"):
            return list(raw.rows)
        if isinstance(raw, dict):
            return list(raw.get("rows", []))
        return list(raw)

    @staticmethod
    def _aggregate(rows: List[Dict[str, Any]], binding: Dict[str, Any]) -> float:
        """按 aggregation 聚合 rows[*][source_property_id]；空集返回 0。"""
        agg = binding.get("aggregation", "count")
        if hasattr(agg, "value"):
            agg = agg.value
        prop = binding.get("source_property_id", "")
        vals = [r.get(prop) for r in rows if r.get(prop) is not None]
        if agg == "count":
            return float(len(rows))
        if agg == "count_distinct":
            return float(len({str(v) for v in vals}))
        if not vals:
            return 0.0
        if agg == "sum":
            return float(sum(vals))
        if agg == "avg":
            return float(sum(vals)) / len(vals)
        if agg == "min":
            return float(min(vals))
        if agg == "max":
            return float(max(vals))
        return 0.0

    @staticmethod
    def _compute_value(
        d: Dict[str, Any], values: Dict[str, float]
    ) -> float:
        """formula 非空则安全求值；否则取首 binding 值。失败降级首 binding。"""
        formula = d.get("formula")
        if not formula:
            return next(iter(values.values())) if values else 0.0
        try:
            return float(_eval_ast(ast.parse(formula, mode="eval").body, values))
        except Exception as e:
            logger.warning(f"formula eval failed, fallback to first binding: {e}")
            return next(iter(values.values())) if values else 0.0

    @staticmethod
    def _build_result(
        d: Dict[str, Any], values: Dict[str, float], value: float
    ) -> Dict[str, Any]:
        return {
            "metric_name": d.get("name", ""),
            "value": value,
            "unit": d.get("unit", ""),
            "precision": int(d.get("precision", 2)),
            "bindings": values,
        }


def _eval_ast(node: ast.AST, values: Dict[str, float]) -> float:
    """AST 白名单递归求值；非白名单节点抛 ValueError。

    白名单：BinOp/UnaryOp/Constant/Name + 算术运算符。
    禁止：Call（__import__/eval）、Attribute（.system）、Subscript 等。
    """
    if isinstance(node, ast.BinOp):
        return _eval_binop(node, values)
    if isinstance(node, ast.UnaryOp):
        return _eval_unaryop(node, values)
    if isinstance(node, ast.Constant):
        return float(node.value)
    if isinstance(node, ast.Name):
        if node.id not in values:
            raise ValueError(f"unknown alias: {node.id}")
        return float(values[node.id])
    raise ValueError(f"unsafe node: {type(node).__name__}")


def _eval_binop(node: ast.BinOp, values: Dict[str, float]) -> float:
    left = _eval_ast(node.left, values)
    right = _eval_ast(node.right, values)
    op = _BIN_OPS.get(type(node.op))
    if op is None:
        raise ValueError(f"unsupported op: {type(node.op).__name__}")
    return float(op(left, right))


def _eval_unaryop(node: ast.UnaryOp, values: Dict[str, float]) -> float:
    operand = _eval_ast(node.operand, values)
    op = _UNARY_OPS.get(type(node.op))
    if op is None:
        raise ValueError(f"unsupported unary: {type(node.op).__name__}")
    return float(op(operand))


__all__ = ["MetricDefinitionService"]
