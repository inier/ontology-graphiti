"""Object View - ViewQueryEngineImpl (T409)

核心流程:
1. OPA 读权限校验 — 注入式 opa_check(view, context) -> bool
2. 数据源加载 — 注入式 data_loader(base_type_id) -> List[Dict]
3. 字段投影 — 只保留 projected_properties 声明的属性
4. 过滤 — 支持 eq/ne/gt/lt/in/contains 简单操作符
5. 排序 — 按 sort_order
6. 行限制 — 应用 row_limit
7. 字段脱敏 — REMOVE / mask_email / mask_ssn / 自定义 pattern
"""
from __future__ import annotations

import logging
import re
from typing import Any, Callable, Dict, List, Optional

from ..interfaces import ViewQueryContext, ViewQueryEngine, ViewQueryResult
from ..models import ObjectView

logger = logging.getLogger(__name__)


OPACheckFn = Callable[[ObjectView, ViewQueryContext], bool]
DataLoaderFn = Callable[[str], List[Dict[str, Any]]]


def _default_opa_check(view: ObjectView, context: ViewQueryContext) -> bool:
    """默认 OPA 校验：拒绝所有（fail-close）"""
    return False


def _default_data_loader(base_type_id: str) -> List[Dict[str, Any]]:
    """默认空数据加载器；调用方应注入真实实现"""
    return []


class AccessDeniedError(PermissionError):
    """OPA 拒绝访问时抛出（由调用方翻译为 HTTP 403）"""

    def __init__(self, message: str = "Access denied by policy"):
        super().__init__(message)
        self.message = message


# 支持的过滤操作符
SUPPORTED_OPERATORS = {"eq", "ne", "gt", "lt", "in", "contains"}


def _op_eq(value, target):
    return value == target


def _op_ne(value, target):
    return value != target


def _op_gt(value, target):
    return value is not None and target is not None and value > target


def _op_lt(value, target):
    return value is not None and target is not None and value < target


def _op_in(value, target):
    if not isinstance(target, (list, tuple, set)):
        return False
    return value in target


def _op_contains(value, target):
    if value is None or target is None:
        return False
    if isinstance(value, str):
        return str(target) in value
    if isinstance(value, (list, tuple, set)):
        return target in value
    return False


_OPERATOR_FUNCS = {
    "eq": _op_eq,
    "ne": _op_ne,
    "gt": _op_gt,
    "lt": _op_lt,
    "in": _op_in,
    "contains": _op_contains,
}


class ViewQueryEngineImpl(ViewQueryEngine):
    """视图查询引擎实现（OPA + 投影 + 过滤 + 排序 + 脱敏）"""

    def __init__(
        self,
        opa_check: OPACheckFn = None,
        data_loader: DataLoaderFn = None,
        permission_provider: Callable[[str, str], Optional[Dict[str, Any]]] = None,
    ):
        self._opa_check = opa_check or _default_opa_check
        self._data_loader = data_loader or _default_data_loader
        self._permission_provider = permission_provider or (
            lambda view_id, role: None
        )

    def set_opa_check(self, opa_check: OPACheckFn) -> None:
        """替换 OPA 校验函数（用于测试或切换策略源）"""
        self._opa_check = opa_check

    def set_data_loader(self, data_loader: DataLoaderFn) -> None:
        """替换数据加载器"""
        self._data_loader = data_loader

    def set_permission_provider(
        self, provider: Callable[[str, str], Optional[Dict[str, Any]]]
    ) -> None:
        """替换权限提供器（view_id, role）→ {redaction_rules, can_export, ...}"""
        self._permission_provider = provider

    def query(self, view: ObjectView, context: ViewQueryContext) -> ViewQueryResult:
        """执行视图查询流水线"""
        if not self._opa_check(view, context):
            raise AccessDeniedError(
                f"OPA denied access for role={context.role} on view={view.id}"
            )
        raw_rows = self._data_loader(view.base_type_id)
        filtered = self._apply_filters(raw_rows, view.filters)
        projected = self._project_rows(filtered, view.projected_properties)
        sorted_rows = self._apply_sort(projected, view.sort_order)
        total = len(sorted_rows)
        truncated = total > view.row_limit
        limited = sorted_rows[: view.row_limit]
        perm = self._permission_provider(view.id, context.role)
        rules = (perm or {}).get("redaction_rules", {}) or {}
        redacted = self._apply_redaction(limited, rules)
        return ViewQueryResult(rows=redacted, total_count=total, truncated=truncated)

    # ---------- 投影 ----------

    @staticmethod
    def _project_rows(
        rows: List[Dict[str, Any]], properties: List[str]
    ) -> List[Dict[str, Any]]:
        """字段投影：仅保留 properties 声明的列（白名单）"""
        if not properties:
            return [dict(r) for r in rows]
        keys = list(properties)
        projected: List[Dict[str, Any]] = []
        for r in rows:
            projected.append({k: r.get(k) for k in keys})
        return projected

    # ---------- 过滤 ----------

    @staticmethod
    def _apply_filters(
        rows: List[Dict[str, Any]], filters: Dict[str, Any]
    ) -> List[Dict[str, Any]]:
        """按 filters 应用过滤条件"""
        if not filters:
            return rows
        compiled = _compile_filters(filters)
        if not compiled:
            return rows
        return [r for r in rows if _row_matches(r, compiled)]

    # ---------- 排序 ----------

    @staticmethod
    def _apply_sort(
        rows: List[Dict[str, Any]], sort_order: List[Dict[str, str]]
    ) -> List[Dict[str, Any]]:
        """按 sort_order 排序（按顺序逐字段稳定排序）"""
        if not sort_order:
            return rows
        sorted_rows = list(rows)
        for spec in reversed(sort_order):
            prop = spec.get("property", "")
            direction = (spec.get("direction") or "asc").lower()
            reverse = direction == "desc"
            # 用 (None→'' 用于字符串, 实际值) 元组做 key 以容忍 None
            sorted_rows.sort(
                key=lambda r, p=prop: (
                    r.get(p) is None,
                    r.get(p) if r.get(p) is not None else "",
                ),
                reverse=reverse,
            )
        return sorted_rows

    # ---------- 脱敏 ----------

    @staticmethod
    def _apply_redaction(
        rows: List[Dict[str, Any]], rules: Dict[str, Any]
    ) -> List[Dict[str, Any]]:
        """按 rules 对每行应用脱敏"""
        if not rules:
            return rows
        out: List[Dict[str, Any]] = []
        for r in rows:
            out.append(_redact_row(r, rules))
        return out


# ============================================================
# 模块级工具函数（拆出来以保证函数体 ≤ 40 行）
# ============================================================


def _compile_filters(filters: Dict[str, Any]) -> List[Dict[str, Any]]:
    """将 filters 编译为 [{property, operator, value}, ...] 列表"""
    compiled: List[Dict[str, Any]] = []
    for prop, expr in filters.items():
        if not isinstance(expr, dict):
            compiled.append({"property": prop, "operator": "eq", "value": expr})
            continue
        for op, val in expr.items():
            op_norm = op.lower()
            if op_norm not in _OPERATOR_FUNCS:
                logger.warning("unsupported filter operator: %s", op)
                continue
            compiled.append(
                {"property": prop, "operator": op_norm, "value": val}
            )
    return compiled


def _row_matches(row: Dict[str, Any], compiled: List[Dict[str, Any]]) -> bool:
    """行是否匹配所有编译后的过滤条件"""
    for cond in compiled:
        func = _OPERATOR_FUNCS[cond["operator"]]
        if not func(row.get(cond["property"]), cond["value"]):
            return False
    return True


def _redact_row(row: Dict[str, Any], rules: Dict[str, Any]) -> Dict[str, Any]:
    """对单行应用全部脱敏规则（REMOVE 真正从 dict 移除）"""
    out = dict(row)
    for path, rule in rules.items():
        key = _strip_jsonpath(path)
        if key not in out:
            continue
        if rule == "REMOVE":
            del out[key]
            continue
        if isinstance(rule, str) and rule in _MASK_FUNCTIONS:
            out[key] = _MASK_FUNCTIONS[rule](out[key])
        elif isinstance(rule, str):
            out[key] = _apply_pattern(out[key], rule)
    return out


def _strip_jsonpath(path: str) -> str:
    """从 '$.foo.bar' 中提取 'foo.bar'"""
    if path.startswith("$."):
        return path[2:]
    return path.lstrip(".")


def _apply_pattern(value: Any, pattern: str) -> str:
    """自定义 pattern：# 占位符保留原字符，其它字符替换为 *"""
    s = str(value)
    if "#" not in pattern:
        return "".join("*" for _ in pattern)
    result_chars: List[str] = []
    src_iter = iter(s)
    for ch in pattern:
        if ch == "#":
            try:
                result_chars.append(next(src_iter))
            except StopIteration:
                result_chars.append("#")
        else:
            result_chars.append("*")
    return "".join(result_chars)


# ---------- 内置脱敏函数 ----------


def _mask_email(value: Any) -> str:
    """保留首字符 + ***@domain"""
    s = str(value)
    if "@" not in s:
        return _apply_pattern(s, "***")
    local, _, domain = s.partition("@")
    first = local[:1] if local else "*"
    return f"{first}***@{domain}"


def _mask_ssn(value: Any) -> str:
    """***-**-#### 保留后 4 位"""
    digits = re.sub(r"\D", "", str(value))
    last4 = digits[-4:] if len(digits) >= 4 else digits
    return "***-**-" + (last4 or "")


_MASK_FUNCTIONS = {
    "mask_email": _mask_email,
    "mask_ssn": _mask_ssn,
}
