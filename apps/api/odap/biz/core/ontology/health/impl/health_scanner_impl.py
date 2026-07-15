"""Data Health - HealthScannerImpl (T338)

实现 5 种规则：
- not_null: 验证属性非空
- unique: 验证属性在类型内唯一
- regex: 正则匹配
- range: 数值范围 (min/max)
- referential_integrity: 外键引用存在

实例数据通过 instance_loader(target_type_id) -> List[Dict] 注入，
便于测试和不同数据源接入。
"""
from __future__ import annotations

import logging
import re
from typing import Any, Callable, Dict, List, Optional

from odap.infra.security.audit_helper import storage_audit

from ..interfaces import HealthRuleRepository, HealthScanner
from ..models import HealthReport, HealthRule, HealthSeverity, HealthStatus
from ..storage import SQLiteHealthStorage
from .health_rule_repository_impl import HealthRuleRepositoryImpl

logger = logging.getLogger(__name__)

_AUDIT_SERVICE = "ontology_design"


def _audit_success(action: str, resource: str = None, details: Dict[str, Any] = None) -> None:
    try:
        storage_audit(
            action=action,
            result_status="success",
            resource=resource,
            details=details or {},
            service=_AUDIT_SERVICE,
        )
    except Exception as e:
        logger.warning(f"audit failed: {e}")


def _audit_failure(action: str, msg: str = "", resource: str = None, details: Dict[str, Any] = None) -> None:
    try:
        storage_audit(
            action=action,
            result_status="failure",
            result_message=(msg or "")[:200],
            resource=resource,
            details=details or {},
            service=_AUDIT_SERVICE,
        )
    except Exception as e:
        logger.warning(f"audit failed: {e}")


InstanceLoader = Callable[[str], List[Dict[str, Any]]]
"""instance_loader(target_type_id) -> List of instance dicts.

Each instance dict must contain at least:
    {"id": "instance-uuid", "type_id": "TypeId", "properties": {...}}
"""


def _default_instance_loader(target_type_id: str) -> List[Dict[str, Any]]:
    """默认空实例加载器；调用方应注入真实实现"""
    return []


class HealthScannerImpl(HealthScanner):
    """5 种规则扫描器实现"""

    def __init__(
        self,
        repository: HealthRuleRepository = None,
        storage: SQLiteHealthStorage = None,
        instance_loader: InstanceLoader = None,
    ):
        self.repository = repository or HealthRuleRepositoryImpl(storage=storage)
        self.storage = storage or SQLiteHealthStorage()
        self._instance_loader = instance_loader or _default_instance_loader

    def set_instance_loader(self, loader: InstanceLoader) -> None:
        """替换实例加载器（用于测试或切换数据源）"""
        self._instance_loader = loader

    def scan(self, rule_id: Optional[str] = None) -> List[HealthReport]:
        """执行扫描；rule_id 为 None 时扫描所有启用规则"""
        action = "health_scanner.scan"
        try:
            if rule_id:
                rule = self.repository.get(rule_id)
                if not rule:
                    _audit_failure(action, msg="rule not found", resource=rule_id,
                                    details={"rule_id": rule_id})
                    return []
                rules = [rule]
            else:
                rules = self.repository.list(enabled_only=True)
            all_reports: List[HealthReport] = []
            rule_failures = 0
            for rule in rules:
                try:
                    reports = self.scan_one(rule)
                except Exception as exc:  # 单条规则失败不影响其他
                    rule_failures += 1
                    logger.exception("scan rule %s failed: %s", rule.id, exc)
                    _audit_failure("health_scanner.scan_one", msg=str(exc),
                                    resource=rule.id, details={"rule_id": rule.id})
                    continue
                for r in reports:
                    self._persist_report(r)
                all_reports.extend(reports)
            pass_count = sum(1 for r in all_reports if r.status == HealthStatus.PASS)
            fail_count = sum(1 for r in all_reports if r.status == HealthStatus.FAIL)
            warn_count = len(all_reports) - pass_count - fail_count
            _audit_success(action, resource=rule_id,
                            details={"rule_id": rule_id or "",
                                     "rules_count": len(rules),
                                     "rule_failures": rule_failures,
                                     "reports_count": len(all_reports),
                                     "pass_count": pass_count,
                                     "warn_count": warn_count,
                                     "fail_count": fail_count})
            return all_reports
        except Exception as exc:
            _audit_failure(action, msg=str(exc), resource=rule_id,
                            details={"rule_id": rule_id or ""})
            raise

    def scan_one(self, rule: HealthRule) -> List[HealthReport]:
        """扫描单条规则"""
        action = "health_scanner.scan_one"
        try:
            checker = _RULE_CHECKERS.get(rule.rule_type)
            if checker is None:
                logger.warning("unknown rule_type=%s; skip", rule.rule_type)
                _audit_failure(action, msg=f"unknown rule_type: {rule.rule_type}",
                                resource=rule.id, details={"rule_id": rule.id,
                                                           "rule_type": rule.rule_type})
                return []
            instances = self._safe_load(rule.target_type_id)
            reports = checker(rule, instances)
            pass_c = sum(1 for r in reports if r.status == HealthStatus.PASS)
            fail_c = sum(1 for r in reports if r.status == HealthStatus.FAIL)
            warn_c = len(reports) - pass_c - fail_c
            _audit_success(action, resource=rule.id,
                            details={"rule_id": rule.id,
                                     "rule_type": rule.rule_type,
                                     "instances_count": len(instances),
                                     "reports_count": len(reports),
                                     "pass_count": pass_c,
                                     "warn_count": warn_c,
                                     "fail_count": fail_c})
            return reports
        except Exception as exc:
            _audit_failure(action, msg=str(exc), resource=rule.id,
                            details={"rule_id": rule.id})
            raise

    # ---------- 持久化 ----------

    def _persist_report(self, report: HealthReport) -> None:
        """将报告写入存储（忽略存储异常）"""
        action = "health_scanner.persist_report"
        try:
            self.storage.save_report(
                {
                    "id": report.id,
                    "rule_id": report.rule_id,
                    "instance_id": report.instance_id,
                    "target_type_id": report.target_type_id,
                    "status": report.status.value,
                    "severity": report.severity.value,
                    "message": report.message,
                    "details": report.details,
                    "scanned_at": report.scanned_at.isoformat(),
                }
            )
        except Exception as exc:  # 持久化失败不阻塞
            logger.warning("save_report failed: %s", exc)
            _audit_failure(action, msg=str(exc), resource=report.id,
                            details={"report_id": report.id,
                                     "rule_id": report.rule_id,
                                     "status": report.status.value})

    def _safe_load(self, target_type_id: str) -> List[Dict[str, Any]]:
        """安全加载实例（loader 异常时返回空列表）"""
        action = "health_scanner.load_instances"
        try:
            results = list(self._instance_loader(target_type_id) or [])
            _audit_success(action,
                            details={"target_type_id_len": len(target_type_id or ""),
                                     "count": len(results)})
            return results
        except Exception as exc:
            logger.warning("instance_loader failed for %s: %s", target_type_id, exc)
            _audit_failure(action, msg=str(exc),
                            details={"target_type_id_len": len(target_type_id or "")})
            return []


# ---------- 5 种规则实现 ----------


def _check_not_null(rule: HealthRule, instances: List[Dict[str, Any]]) -> List[HealthReport]:
    """not_null: check_expression.properties 指定不能为空的字段名列表"""
    properties: List[str] = rule.check_expression.get("properties", []) or []
    reports: List[HealthReport] = []
    for inst in instances:
        iid = str(inst.get("id", ""))
        props = inst.get("properties", {}) or {}
        missing = [p for p in properties if props.get(p) in (None, "")]
        if missing:
            reports.append(
                _make_report(
                    rule, iid, HealthStatus.FAIL,
                    f"Missing required properties: {missing}",
                    {"missing": missing, "actual_properties": list(props.keys())},
                )
            )
        else:
            reports.append(
                _make_report(rule, iid, HealthStatus.PASS, "All required properties present")
            )
    return reports


def _check_unique(rule: HealthRule, instances: List[Dict[str, Any]]) -> List[HealthReport]:
    """unique: check_expression.properties 指定唯一性字段（仅在同类型内）"""
    properties: List[str] = rule.check_expression.get("properties", []) or []
    target_type = rule.target_type_id
    type_instances = [i for i in instances if i.get("type_id") == target_type]
    reports: List[HealthReport] = []
    for prop in properties:
        seen: Dict[Any, str] = {}
        duplicates: List[Dict[str, Any]] = []
        for inst in type_instances:
            iid = str(inst.get("id", ""))
            val = (inst.get("properties", {}) or {}).get(prop)
            if val in (None, ""):
                continue
            if val in seen:
                duplicates.append({"value": val, "first_id": seen[val], "second_id": iid})
            else:
                seen[val] = iid
        if duplicates:
            for dup in duplicates:
                reports.append(
                    _make_report(
                        rule, dup["second_id"], HealthStatus.FAIL,
                        f"Duplicate {prop!r}={dup['value']!r} (first={dup['first_id']})",
                        {"property": prop, "value": dup["value"], "first_id": dup["first_id"]},
                    )
                )
        else:
            for inst in type_instances:
                reports.append(
                    _make_report(
                        rule, str(inst.get("id", "")), HealthStatus.PASS,
                        f"Property {prop!r} is unique within type",
                    )
                )
    return reports


def _check_regex(rule: HealthRule, instances: List[Dict[str, Any]]) -> List[HealthReport]:
    """regex: check_expression.property 字段 + check_expression.pattern 正则"""
    prop = rule.check_expression.get("property", "")
    pattern = rule.check_expression.get("pattern", "")
    compiled, err = _compile_regex(pattern)
    if not prop or not pattern:
        return [
            _make_report(
                rule, "<rule>", HealthStatus.FAIL,
                "regex rule missing 'property' or 'pattern'",
            )
        ]
    if err is not None:
        return [
            _make_report(
                rule, "<rule>", HealthStatus.FAIL,
                f"Invalid regex pattern: {err}",
            )
        ]
    return [_evaluate_regex_instance(rule, inst, prop, compiled) for inst in instances]


def _compile_regex(pattern: str):
    """编译正则；返回 (compiled, error_message)"""
    try:
        return re.compile(pattern), None
    except re.error as exc:
        return None, str(exc)


def _evaluate_regex_instance(
    rule: HealthRule,
    inst: Dict[str, Any],
    prop: str,
    compiled: "re.Pattern",
) -> HealthReport:
    """对单个实例做正则校验"""
    iid = str(inst.get("id", ""))
    val = (inst.get("properties", {}) or {}).get(prop)
    if val in (None, ""):
        return _make_report(
            rule, iid, HealthStatus.FAIL,
            f"Property {prop!r} is empty",
            {"property": prop},
        )
    if not compiled.search(str(val)):
        return _make_report(
            rule, iid, HealthStatus.FAIL,
            f"Property {prop!r}={val!r} does not match pattern",
            {"property": prop, "value": val},
        )
    return _make_report(rule, iid, HealthStatus.PASS, f"{prop!r} matches pattern")


def _check_range(rule: HealthRule, instances: List[Dict[str, Any]]) -> List[HealthReport]:
    """range: check_expression.property + min/max 数值范围

    - 值 < min 或 > max → FAIL
    - 值在 [min, min+10%) 或 [max-10%, max] → WARN (边界警告)
    """
    prop = rule.check_expression.get("property", "")
    minimum = rule.check_expression.get("min")
    maximum = rule.check_expression.get("max")
    return [_evaluate_range_instance(rule, inst, prop, minimum, maximum) for inst in instances]


def _evaluate_range_instance(
    rule: HealthRule,
    inst: Dict[str, Any],
    prop: str,
    minimum,
    maximum,
) -> HealthReport:
    """对单个实例做 range 校验"""
    iid = str(inst.get("id", ""))
    val = (inst.get("properties", {}) or {}).get(prop)
    if val in (None, "") or not isinstance(val, (int, float)):
        return _make_report(
            rule, iid, HealthStatus.FAIL,
            f"Property {prop!r} is empty or non-numeric",
            {"property": prop, "value": val},
        )
    if minimum is not None and val < minimum:
        return _make_report(
            rule, iid, HealthStatus.FAIL,
            f"{prop!r}={val} < min={minimum}",
            {"property": prop, "value": val, "min": minimum},
        )
    if maximum is not None and val > maximum:
        return _make_report(
            rule, iid, HealthStatus.FAIL,
            f"{prop!r}={val} > max={maximum}",
            {"property": prop, "value": val, "max": maximum},
        )
    if _is_near_edge(val, minimum, maximum):
        return _make_report(
            rule, iid, HealthStatus.WARN,
            f"{prop!r}={val} is near edge of [{minimum},{maximum}]",
            {"property": prop, "value": val},
        )
    return _make_report(rule, iid, HealthStatus.PASS, f"{prop!r} within range")


def _check_referential_integrity(
    rule: HealthRule, instances: List[Dict[str, Any]]
) -> List[HealthReport]:
    """referential_integrity: check_expression.property 引用 + ref_type_id 目标类型

    仅校验 ref 字段值非空；外键存在性由 instance_loader 提供 ref 索引或
    全部目标类型实例列表。
    """
    prop = rule.check_expression.get("property", "")
    ref_type_id = rule.check_expression.get("ref_type_id", "")
    return [
        _evaluate_ref_instance(rule, inst, prop, ref_type_id) for inst in instances
    ]


def _evaluate_ref_instance(
    rule: HealthRule,
    inst: Dict[str, Any],
    prop: str,
    ref_type_id: str,
) -> HealthReport:
    """对单个实例做 referential_integrity 校验"""
    iid = str(inst.get("id", ""))
    val = (inst.get("properties", {}) or {}).get(prop)
    if val in (None, ""):
        return _make_report(
            rule, iid, HealthStatus.FAIL,
            f"Reference {prop!r} is empty",
            {"property": prop, "ref_type_id": ref_type_id},
        )
    ref_ids: List[str] = val if isinstance(val, list) else [val]
    resolved_key = f"{prop}_resolved"
    resolved = (inst.get("properties", {}) or {}).get(resolved_key, [])
    if not isinstance(resolved, list):
        resolved = []
    for rid in ref_ids:
        if rid not in resolved:
            return _make_report(
                rule, iid, HealthStatus.FAIL,
                f"Reference {prop!r}={rid!r} not found in {ref_type_id!r}",
                {"property": prop, "ref_value": rid, "ref_type_id": ref_type_id},
            )
    return _make_report(
        rule, iid, HealthStatus.PASS,
        f"Reference {prop!r} resolved in {ref_type_id!r}",
    )


def _is_near_edge(value: float, minimum, maximum) -> bool:
    """判断 value 是否接近 [min, max] 边界（10% 容差）"""
    if minimum is None and maximum is None:
        return False
    if minimum is not None:
        margin_min = abs(value - minimum) / max(abs(minimum), 1)
        if 0 <= margin_min <= 0.1:
            return True
    if maximum is not None:
        margin_max = abs(maximum - value) / max(abs(maximum), 1)
        if 0 <= margin_max <= 0.1:
            return True
    return False


def _make_report(
    rule: HealthRule,
    instance_id: str,
    status: HealthStatus,
    message: str,
    details: Optional[Dict[str, Any]] = None,
) -> HealthReport:
    """构造 HealthReport 工具方法"""
    return HealthReport(
        rule_id=rule.id,
        instance_id=instance_id,
        target_type_id=rule.target_type_id,
        status=status,
        severity=rule.severity,
        message=message,
        details=details or {},
    )


# 规则类型 → 校验函数映射
_RULE_CHECKERS: Dict[str, Any] = {
    "not_null": _check_not_null,
    "unique": _check_unique,
    "regex": _check_regex,
    "range": _check_range,
    "referential_integrity": _check_referential_integrity,
}
