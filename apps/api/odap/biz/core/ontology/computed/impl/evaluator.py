"""SafeExpressionEvaluator (T394)

安全沙箱表达式求值器：
- AST 白名单 + compile + eval
- 禁止: 文件 I/O、网络、exec/eval、任意对象访问、import
- 支持: 数学 (+-*/)、sum/avg/min/max、字符串 concat/upper/lower/length/substring、
        日期 now/date_diff/date_add、聚合 (sum_field/avg_field/min_field/max_field over
        collections of dicts)、条件 if/case

DSL 风格示例（属性访问使用 instance / properties 前缀，内部转换为 [] 访问）:
- 数学: "instance.score * 2"
- 字符串: "concat(instance.first_name, ' ', instance.last_name)"
- 聚合: "sum_field(instance.items, 'amount')"
- 条件: "if(instance.amount > 100, instance.amount * 0.9, instance.amount)"
"""
from __future__ import annotations

import ast
import math
import re
from datetime import datetime, timedelta
from typing import Any, Dict, List

from ..interfaces import EvaluationContext, ExpressionEvaluator, ValidationResult


_ALLOWED_NODES: tuple = (
    ast.Expression, ast.Module,
    ast.Constant, ast.Num, ast.Str, ast.Name, ast.Load,
    ast.BinOp, ast.UnaryOp, ast.BoolOp,
    ast.Add, ast.Sub, ast.Mult, ast.Div, ast.FloorDiv, ast.Mod, ast.Pow,
    ast.USub, ast.UAdd, ast.Not,
    ast.And, ast.Or,
    ast.Compare, ast.Eq, ast.NotEq, ast.Lt, ast.LtE, ast.Gt, ast.GtE,
    ast.IfExp,
    ast.Call, ast.keyword,
    ast.Attribute,
    ast.List, ast.Tuple, ast.Dict,
    ast.Subscript, ast.Index,
    ast.Lambda,
    ast.JoinedStr, ast.FormattedValue,
    ast.Load,
)

_BANNED_NAMES: frozenset = frozenset({
    "__import__", "exec", "eval", "compile", "open",
    "globals", "locals", "vars", "dir",
    "getattr", "setattr", "delattr", "hasattr",
    "__builtins__", "input", "breakpoint", "memoryview",
    "object", "type", "super", "property",
})


class AttrDict(dict):
    """支持属性访问的 dict：`ad.amount == ad['amount']`

    关键：__getattribute__ 优先从 dict 查找，避免被 dict 内置方法
    (items / keys / values / get / pop / update ...) 屏蔽用户的字段名。
    """

    def __getattr__(self, key: str) -> Any:
        if key.startswith("_"):
            raise AttributeError(key)
        try:
            return self[key]
        except KeyError as exc:
            raise AttributeError(key) from exc

    def __getattribute__(self, key: str) -> Any:
        # dunder 走正常路径（不要拦截）
        if key.startswith("__") and key.endswith("__"):
            return super().__getattribute__(key)
        # 优先从 dict 键值查找
        try:
            return dict.__getitem__(self, key)
        except KeyError:
            pass
        return super().__getattribute__(key)

    def __setattr__(self, key: str, value: Any) -> None:
        self[key] = value


def _to_attr_dict(value: Any) -> Any:
    """递归把 dict → AttrDict, 保留 list 原样"""
    if isinstance(value, dict):
        return AttrDict({k: _to_attr_dict(v) for k, v in value.items()})
    if isinstance(value, list):
        return [_to_attr_dict(v) for v in value]
    return value


class SafeExpressionEvaluator(ExpressionEvaluator):
    """安全沙箱表达式求值器"""

    MAX_EXPR_LEN = 2000

    def evaluate(
        self, expression: str, context: EvaluationContext
    ) -> Any:
        """对单个实例求值"""
        if not isinstance(expression, str) or not expression.strip():
            raise ValueError("expression must be a non-empty string")
        if len(expression) > self.MAX_EXPR_LEN:
            raise ValueError("expression too long")
        self._validate_ast(expression)
        code = compile(expression, "<computed_expr>", "eval")
        safe_globals = self._build_safe_globals()
        local_ns = self._build_local_ns(context)
        return eval(code, safe_globals, local_ns)

    def validate(self, expression: str) -> ValidationResult:
        """校验表达式语法 + 提取依赖"""
        if not isinstance(expression, str) or not expression.strip():
            return ValidationResult(False, "expression is empty")
        if len(expression) > self.MAX_EXPR_LEN:
            return ValidationResult(False, "expression too long")
        try:
            self._validate_ast(expression)
        except ValueError as exc:
            return ValidationResult(False, str(exc))
        deps = self.extract_dependencies(expression)
        return ValidationResult(True, "", deps)

    def extract_dependencies(self, expression: str) -> List[str]:
        """从表达式中提取依赖属性名（保序去重）"""
        try:
            tree = ast.parse(expression, mode="eval")
        except SyntaxError:
            return []
        deps: List[str] = []
        seen: set = set()
        for node in ast.walk(tree):
            name = self._attr_or_name(node)
            if name and re.match(r"^[A-Za-z_][A-Za-z0-9_]*$", name):
                if name not in seen:
                    seen.add(name)
                    deps.append(name)
        return deps

    def _validate_ast(self, expression: str) -> None:
        """AST 白名单校验"""
        try:
            tree = ast.parse(expression, mode="eval")
        except SyntaxError as exc:
            raise ValueError(f"syntax error: {exc.msg}")
        for node in ast.walk(tree):
            if not isinstance(node, _ALLOWED_NODES):
                raise ValueError(
                    f"disallowed AST node: {type(node).__name__}"
                )
            if isinstance(node, ast.Name) and node.id in _BANNED_NAMES:
                raise ValueError(f"banned name: {node.id}")
            if isinstance(node, ast.Attribute):
                head = self._attr_head_name(node)
                if head in _BANNED_NAMES:
                    raise ValueError(f"banned attribute access: {head}")

    @staticmethod
    def _attr_or_name(node) -> str:
        if isinstance(node, ast.Name):
            return node.id
        if isinstance(node, ast.Attribute):
            return node.attr
        return ""

    @staticmethod
    def _attr_head_name(node: ast.Attribute) -> str:
        cur: Any = node
        while isinstance(cur, ast.Attribute):
            cur = cur.value
        if isinstance(cur, ast.Name):
            return cur.id
        return ""

    def _build_safe_globals(self) -> Dict[str, Any]:
        """构造安全的 globals 字典（仅暴露内置函数）"""
        funcs = self._builtin_functions()
        return {
            "__builtins__": {},
            **funcs,
        }

    @staticmethod
    def _build_local_ns(context: EvaluationContext) -> Dict[str, Any]:
        """构造求值 locals（instance / properties）"""
        return {
            "instance": _to_attr_dict(context.instance or {}),
            "properties": _to_attr_dict(context.properties or {}),
        }

    @staticmethod
    def _builtin_functions() -> Dict[str, Any]:
        """内置函数（白名单）—— 注册到求值 globals 的函数集合"""
        return _BUILTIN_FUNCTIONS


def _lookup_field(item: Any, field: str) -> Any:
    """支持 item[field] / item.field 两种形式"""
    if isinstance(item, dict):
        if field in item:
            return item[field]
    return getattr(item, field, None)


def _coerce_dt(value: Any):
    """尝试将 value 解析为 datetime；失败返回 None"""
    if isinstance(value, datetime):
        return value
    if not value:
        return None
    try:
        return datetime.fromisoformat(str(value))
    except (TypeError, ValueError):
        return None


# ---------------------------------------------------------------------------
# Built-in functions exposed to expression evaluator.
# Each helper is a small module-level function (< 40 lines) so the registry
# itself can be expressed as a flat dict literal.
# ---------------------------------------------------------------------------


def _bf_sum(values, default=0):
    """sum() with default fallback for empty input."""
    values = list(values or [])
    return sum(values) if values else default


def _bf_avg(values, default=0):
    """avg() across numeric values; ignores non-numeric entries."""
    values = [v for v in (values or []) if isinstance(v, (int, float))]
    return (sum(values) / len(values)) if values else default


def _bf_min(values, default=None):
    """min() with default fallback for empty input."""
    values = list(values or [])
    return min(values) if values else default


def _bf_max(values, default=None):
    """max() with default fallback for empty input."""
    values = list(values or [])
    return max(values) if values else default


def _bf_count(values):
    """len() of values; tolerates None."""
    return len(list(values or []))


def _bf_sum_field(items, field, default=0):
    """Sum numeric values of `field` across `items`."""
    if not items:
        return default
    total = 0
    for it in items:
        v = _lookup_field(it, field)
        if isinstance(v, (int, float)):
            total += v
    return total


def _bf_avg_field(items, field, default=0):
    """Average numeric values of `field` across `items`."""
    if not items:
        return default
    vals = [
        v for v in (_lookup_field(it, field) for it in items)
        if isinstance(v, (int, float))
    ]
    return (sum(vals) / len(vals)) if vals else default


def _bf_min_field(items, field, default=None):
    """Min value of `field` across `items`; ignores None entries."""
    if not items:
        return default
    vals = [
        v for v in (_lookup_field(it, field) for it in items)
        if v is not None
    ]
    return min(vals) if vals else default


def _bf_max_field(items, field, default=None):
    """Max value of `field` across `items`; ignores None entries."""
    if not items:
        return default
    vals = [
        v for v in (_lookup_field(it, field) for it in items)
        if v is not None
    ]
    return max(vals) if vals else default


def _bf_concat(*args):
    """Concatenate args to a single string; flattens list/tuple args."""
    parts = []
    for a in args:
        if a is None:
            parts.append("")
        elif isinstance(a, (list, tuple)):
            parts.extend(str(x) for x in a)
        else:
            parts.append(str(a))
    return "".join(parts)


def _bf_upper(s):
    """str(s).upper(); tolerates None."""
    return str(s or "").upper()


def _bf_lower(s):
    """str(s).lower(); tolerates None."""
    return str(s or "").lower()


def _bf_length(s):
    """len(s); returns 0 for None or non-sized values."""
    if s is None:
        return 0
    try:
        return len(s)
    except TypeError:
        return 0


def _bf_substring(s, start, end=None):
    """s[start:end]; coerces to str and tolerates None."""
    text = str(s or "")
    if end is None:
        return text[int(start):]
    return text[int(start):int(end)]


def _bf_now():
    """Current local datetime as ISO string."""
    return datetime.now().isoformat()


def _bf_date_diff(a, b, unit="days"):
    """Difference between two ISO datetimes; units: seconds/minutes/hours/days."""
    da = _coerce_dt(a)
    db = _coerce_dt(b)
    if da is None or db is None:
        return 0
    delta = db - da
    if unit == "seconds":
        return delta.total_seconds()
    if unit == "minutes":
        return delta.total_seconds() / 60
    if unit == "hours":
        return delta.total_seconds() / 3600
    return delta.days


def _bf_date_add(a, days=0, seconds=0):
    """Add days/seconds to a datetime; returns ISO string."""
    da = _coerce_dt(a) or datetime.now()
    return (da + timedelta(days=int(days), seconds=int(seconds))).isoformat()


def _bf_iif(cond, a, b):
    """Immediate IF (避开 Python 关键字 if)."""
    return a if cond else b


def _bf_case(*args):
    """case(cond1, v1, cond2, v2, ..., default) — odd args are values."""
    for i in range(0, len(args) - 1, 2):
        if args[i]:
            return args[i + 1]
    return args[-1] if args and len(args) % 2 == 1 else None


_BUILTIN_FUNCTIONS: Dict[str, Any] = {
    "sum": _bf_sum,
    "avg": _bf_avg,
    "min": _bf_min,
    "max": _bf_max,
    "count": _bf_count,
    "sum_field": _bf_sum_field,
    "avg_field": _bf_avg_field,
    "min_field": _bf_min_field,
    "max_field": _bf_max_field,
    "concat": _bf_concat,
    "upper": _bf_upper,
    "lower": _bf_lower,
    "length": _bf_length,
    "substring": _bf_substring,
    "now": _bf_now,
    "date_diff": _bf_date_diff,
    "date_add": _bf_date_add,
    "iif": _bf_iif,
    "case": _bf_case,
    "pi": math.pi,
    "e": math.e,
    "round": round,
    "abs": abs,
    "int": int,
    "float": float,
    "str": str,
    "bool": bool,
    "len": len,
    "True": True,
    "False": False,
    "None": None,
}


__all__ = ["SafeExpressionEvaluator", "AttrDict"]
