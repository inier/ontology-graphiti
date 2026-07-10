"""Data Health - HealthService 编排层 (T340)

服务层规范（AGENTS.md 规则 2）：
- 必须返回 Dict[str, Any]，禁止抛 HTTPException
- 错误格式: {"status": "error", "message": "..."}
- 成功格式: 扁平 dict
- 类型转换: Enum→.value, datetime→.isoformat(), BaseModel→扁平 dict
"""
from __future__ import annotations

import logging
from typing import Any, Dict, List, Optional

from odap.infra.security.audit_helper import storage_audit

from ..impl import HealthRuleRepositoryImpl, HealthScannerImpl, NotificationDispatcher
from ..models import (
    HealthReport,
    HealthRule,
    HealthSeverity,
    HealthStatus,
)
from ..storage import SQLiteHealthStorage

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


class HealthService:
    """健康规则编排服务"""

    def __init__(
        self,
        repository: HealthRuleRepositoryImpl = None,
        scanner: HealthScannerImpl = None,
        storage: SQLiteHealthStorage = None,
        notifier: NotificationDispatcher = None,
    ):
        self.storage = storage or SQLiteHealthStorage()
        self.repository = repository or HealthRuleRepositoryImpl(storage=self.storage)
        self.scanner = scanner or HealthScannerImpl(
            repository=self.repository, storage=self.storage
        )
        self.notifier = notifier or NotificationDispatcher()

    # ---------- 规则 CRUD ----------

    def create_rule(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        """创建规则"""
        action = "health.create_rule"
        try:
            rule = self._build_rule(payload, new_id=True)
            self.repository.save(rule)
            _audit_success(action, resource=rule.id,
                            details={"rule_id": rule.id,
                                     "rule_type": rule.rule_type,
                                     "severity": rule.severity.value,
                                     "target_type_id_len": len(rule.target_type_id or ""),
                                     "enabled": rule.enabled})
            return self._rule_to_dict(rule)
        except ValueError as exc:
            _audit_failure(action, msg=str(exc),
                            details={"target_type_id_len": len(payload.get("target_type_id", "") or "")})
            return {"status": "error", "message": str(exc)}
        except Exception as exc:
            _audit_failure(action, msg=str(exc))
            return {"status": "error", "message": f"create_rule failed: {exc}"}

    def get_rule(self, rule_id: str) -> Dict[str, Any]:
        """获取规则"""
        action = "health.get_rule"
        try:
            rule = self.repository.get(rule_id)
            if not rule:
                _audit_failure(action, msg="rule not found", resource=rule_id,
                                details={"rule_id": rule_id})
                return {"status": "error", "message": f"rule not found: {rule_id}"}
            _audit_success(action, resource=rule_id,
                            details={"rule_id": rule_id,
                                     "rule_type": rule.rule_type,
                                     "severity": rule.severity.value,
                                     "enabled": rule.enabled})
            return self._rule_to_dict(rule)
        except Exception as exc:
            _audit_failure(action, msg=str(exc), resource=rule_id,
                            details={"rule_id": rule_id})
            return {"status": "error", "message": f"get_rule failed: {exc}"}

    def list_rules(
        self,
        enabled_only: bool = False,
        target_type_id: Optional[str] = None,
        severity: Optional[str] = None,
    ) -> Dict[str, Any]:
        """列出规则；支持按 enabled / target_type_id / severity 过滤"""
        action = "health.list_rules"
        try:
            if target_type_id:
                rules = self.repository.list_by_target_type(target_type_id)
            elif severity:
                try:
                    sev_enum = HealthSeverity(severity)
                except ValueError:
                    _audit_failure(action, msg=f"unknown severity: {severity}",
                                    details={"severity": str(severity)})
                    return {"status": "error", "message": f"unknown severity: {severity}"}
                rules = self.repository.list_by_severity(sev_enum)
            else:
                rules = self.repository.list(enabled_only=enabled_only)
            _audit_success(action,
                            details={"enabled_only": enabled_only,
                                     "has_target_type_filter": bool(target_type_id),
                                     "has_severity_filter": bool(severity),
                                     "count": len(rules)})
            return {
                "rules": [self._rule_to_dict(r) for r in rules],
                "count": len(rules),
            }
        except Exception as exc:
            _audit_failure(action, msg=str(exc))
            return {"status": "error", "message": f"list_rules failed: {exc}"}

    def update_rule(self, rule_id: str, payload: Dict[str, Any]) -> Dict[str, Any]:
        """更新规则"""
        action = "health.update_rule"
        try:
            existing = self.repository.get(rule_id)
            if not existing:
                _audit_failure(action, msg="rule not found", resource=rule_id,
                                details={"rule_id": rule_id})
                return {"status": "error", "message": f"rule not found: {rule_id}"}
            merged = self._merge_rule(existing, payload)
            self.repository.save(merged)
            _audit_success(action, resource=rule_id,
                            details={"rule_id": rule_id,
                                     "enabled": merged.enabled,
                                     "rule_type": merged.rule_type})
            return self._rule_to_dict(merged)
        except ValueError as exc:
            _audit_failure(action, msg=str(exc), resource=rule_id,
                            details={"rule_id": rule_id})
            return {"status": "error", "message": str(exc)}
        except Exception as exc:
            _audit_failure(action, msg=str(exc), resource=rule_id,
                            details={"rule_id": rule_id})
            return {"status": "error", "message": f"update_rule failed: {exc}"}

    def delete_rule(self, rule_id: str) -> Dict[str, Any]:
        """删除规则"""
        action = "health.delete_rule"
        try:
            ok = self.repository.delete(rule_id)
            if not ok:
                _audit_failure(action, msg="rule not found", resource=rule_id,
                                details={"rule_id": rule_id})
                return {"status": "error", "message": f"rule not found: {rule_id}"}
            _audit_success(action, resource=rule_id,
                            details={"rule_id": rule_id, "deleted": True})
            return {"rule_id": rule_id, "deleted": True}
        except Exception as exc:
            _audit_failure(action, msg=str(exc), resource=rule_id,
                            details={"rule_id": rule_id})
            return {"status": "error", "message": f"delete_rule failed: {exc}"}

    # ---------- 扫描 ----------

    def trigger_scan(self, rule_id: Optional[str] = None) -> Dict[str, Any]:
        """触发扫描；返回聚合结果 + reports 列表"""
        action = "health.trigger_scan"
        try:
            reports: List[HealthReport] = self.scanner.scan(rule_id)
            counts = self._count_by_status(reports)
            payload = {
                "scanned_count": len(reports),
                "pass_count": counts.get(HealthStatus.PASS, 0),
                "warn_count": counts.get(HealthStatus.WARN, 0),
                "fail_count": counts.get(HealthStatus.FAIL, 0),
                "reports": [self._report_to_dict(r) for r in reports],
            }
            if rule_id:
                payload["rule_id"] = rule_id
            # 触发失败告警通知（非阻塞）
            self._maybe_notify(rule_id, reports)
            _audit_success(action, resource=rule_id,
                            details={"rule_id": rule_id or "",
                                     "scanned_count": len(reports),
                                     "pass_count": counts.get(HealthStatus.PASS, 0),
                                     "warn_count": counts.get(HealthStatus.WARN, 0),
                                     "fail_count": counts.get(HealthStatus.FAIL, 0)})
            return payload
        except Exception as exc:
            logger.exception("trigger_scan failed")
            _audit_failure(action, msg=str(exc),
                            details={"rule_id": rule_id or ""})
            return {"status": "error", "message": f"trigger_scan failed: {exc}"}

    # ---------- 报告查询 ----------

    def list_reports(
        self,
        status: Optional[str] = None,
        severity: Optional[str] = None,
        target_type_id: Optional[str] = None,
        limit: int = 100,
        offset: int = 0,
    ) -> Dict[str, Any]:
        """列出报告（支持 status/severity/target_type_id 过滤）"""
        action = "health.list_reports"
        try:
            if status:
                try:
                    HealthStatus(status)
                except ValueError:
                    _audit_failure(action, msg=f"unknown status: {status}",
                                    details={"status": str(status)})
                    return {"status": "error", "message": f"unknown status: {status}"}
            if severity:
                try:
                    HealthSeverity(severity)
                except ValueError:
                    _audit_failure(action, msg=f"unknown severity: {severity}",
                                    details={"severity": str(severity)})
                    return {"status": "error", "message": f"unknown severity: {severity}"}
            rows = self.storage.list_reports(
                status=status,
                severity=severity,
                target_type_id=target_type_id,
                limit=limit,
                offset=offset,
            )
            total = self.storage.count_reports(
                status=status, severity=severity, target_type_id=target_type_id
            )
            _audit_success(action,
                            details={"has_status_filter": bool(status),
                                     "has_severity_filter": bool(severity),
                                     "has_target_type_filter": bool(target_type_id),
                                     "count": len(rows),
                                     "total": total})
            return {
                "reports": [self._row_to_report_dict(r) for r in rows],
                "count": len(rows),
                "total": total,
                "limit": limit,
                "offset": offset,
            }
        except Exception as exc:
            _audit_failure(action, msg=str(exc))
            return {"status": "error", "message": f"list_reports failed: {exc}"}

    def get_report(self, report_id: str) -> Dict[str, Any]:
        """获取单条报告"""
        action = "health.get_report"
        try:
            row = self.storage.get_report(report_id)
            if not row:
                _audit_failure(action, msg="report not found", resource=report_id,
                                details={"report_id": report_id})
                return {"status": "error", "message": f"report not found: {report_id}"}
            _audit_success(action, resource=report_id,
                            details={"report_id": report_id,
                                     "status": row.get("status", "")})
            return self._row_to_report_dict(row)
        except Exception as exc:
            _audit_failure(action, msg=str(exc), resource=report_id,
                            details={"report_id": report_id})
            return {"status": "error", "message": f"get_report failed: {exc}"}

    # ---------- 内部工具 ----------

    @staticmethod
    def _build_rule(payload: Dict[str, Any], new_id: bool) -> HealthRule:
        """从 payload 构造 HealthRule；进行字段校验"""
        name = payload.get("name")
        target_type_id = payload.get("target_type_id")
        if not name:
            raise ValueError("name is required")
        if not target_type_id:
            raise ValueError("target_type_id is required")
        rule_type = payload.get("rule_type", "not_null")
        severity = payload.get("severity", "warning")
        if rule_type not in {
            "not_null", "unique", "regex", "range", "referential_integrity"
        }:
            raise ValueError(f"unknown rule_type: {rule_type}")
        try:
            severity_enum = HealthSeverity(severity)
        except ValueError:
            raise ValueError(f"unknown severity: {severity}")
        rule_id = payload.get("id") if not new_id else None
        return HealthRule(
            id=rule_id or payload.get("id") or _new_id(),
            target_type_id=target_type_id,
            name=name,
            description=payload.get("description", ""),
            rule_type=rule_type,
            check_expression=payload.get("check_expression", {}) or {},
            severity=severity_enum,
            schedule=payload.get("schedule", "") or "",
            notification_channel=payload.get("notification_channel", {}) or {},
            enabled=bool(payload.get("enabled", True)),
        )

    @staticmethod
    def _merge_rule(existing: HealthRule, payload: Dict[str, Any]) -> HealthRule:
        """合并更新字段；不传则保留原值"""
        merged_payload = {
            "id": existing.id,
            "name": payload.get("name", existing.name),
            "target_type_id": payload.get("target_type_id", existing.target_type_id),
            "description": payload.get("description", existing.description),
            "rule_type": payload.get("rule_type", existing.rule_type),
            "check_expression": payload.get("check_expression", existing.check_expression),
            "severity": payload.get("severity", existing.severity.value),
            "schedule": payload.get("schedule", existing.schedule),
            "notification_channel": payload.get(
                "notification_channel", existing.notification_channel
            ),
            "enabled": payload.get("enabled", existing.enabled),
        }
        return HealthService._build_rule(merged_payload, new_id=False)

    @staticmethod
    def _rule_to_dict(rule: HealthRule) -> Dict[str, Any]:
        """HealthRule → 扁平 dict"""
        return {
            "id": rule.id,
            "target_type_id": rule.target_type_id,
            "name": rule.name,
            "description": rule.description,
            "rule_type": rule.rule_type,
            "check_expression": rule.check_expression,
            "severity": rule.severity.value,
            "schedule": rule.schedule,
            "notification_channel": rule.notification_channel,
            "enabled": rule.enabled,
            "created_at": rule.created_at.isoformat(),
            "updated_at": rule.updated_at.isoformat(),
        }

    @staticmethod
    def _report_to_dict(report: HealthReport) -> Dict[str, Any]:
        """HealthReport → 扁平 dict"""
        return {
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

    @staticmethod
    def _row_to_report_dict(row: Dict[str, Any]) -> Dict[str, Any]:
        """storage row → 报告 dict（datetime 字段是 ISO 字符串）"""
        scanned_at = row.get("scanned_at", "")
        return {
            "id": row.get("id", ""),
            "rule_id": row.get("rule_id", ""),
            "instance_id": row.get("instance_id", ""),
            "target_type_id": row.get("target_type_id", ""),
            "status": row.get("status", "pass"),
            "severity": row.get("severity", "warning"),
            "message": row.get("message", ""),
            "details": row.get("details", {}) or {},
            "scanned_at": scanned_at,
        }

    @staticmethod
    def _count_by_status(reports: List[HealthReport]) -> Dict[HealthStatus, int]:
        """按 status 分组统计"""
        counts: Dict[HealthStatus, int] = {
            HealthStatus.PASS: 0,
            HealthStatus.WARN: 0,
            HealthStatus.FAIL: 0,
        }
        for r in reports:
            counts[r.status] = counts.get(r.status, 0) + 1
        return counts

    def _maybe_notify(
        self, rule_id: Optional[str], reports: List[HealthReport]
    ) -> None:
        """对有失败报告的规则触发通知（fire-and-forget）"""
        try:
            failed = [r for r in reports if r.status == HealthStatus.FAIL]
            if not failed:
                return
            # 找到对应规则
            target_rules: List[HealthRule] = []
            if rule_id:
                r = self.repository.get(rule_id)
                if r:
                    target_rules = [r]
            else:
                # 取所有启用的、且有失败报告的规则
                rule_ids = {r.rule_id for r in failed}
                for rid in rule_ids:
                    r = self.repository.get(rid)
                    if r and r.enabled and r.notification_channel:
                        target_rules.append(r)
            for r in target_rules:
                if r.notification_channel:
                    self.notifier.dispatch(
                        r.notification_channel,
                        subject=f"[Health] {r.name} - {len(failed)} failures",
                        body=f"Rule {r.name} (id={r.id}) produced {len(failed)} failing reports.",
                        reports=[self._report_to_dict(rp) for rp in failed if rp.rule_id == r.id],
                    )
        except Exception as exc:  # 通知失败不阻塞主流程
            logger.warning("notify failed: %s", exc)


def _new_id() -> str:
    """生成 UUID 字符串"""
    import uuid
    return str(uuid.uuid4())
