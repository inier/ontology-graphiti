"""Data Health - HealthRuleRepositoryImpl (T337)

实现 HealthRuleRepository 的 6 个抽象方法，
依赖 SQLiteHealthStorage 持久化。
"""
from __future__ import annotations

from datetime import datetime
from typing import List, Optional

from ..interfaces import HealthRuleRepository
from ..models import HealthRule, HealthSeverity
from ..storage import SQLiteHealthStorage


class HealthRuleRepositoryImpl(HealthRuleRepository):
    """健康规则仓储实现（基于 SQLite）"""

    def __init__(self, storage: SQLiteHealthStorage = None):
        self.storage = storage or SQLiteHealthStorage()

    def save(self, rule: HealthRule) -> HealthRule:
        """保存或更新规则（upsert）"""
        rule.updated_at = datetime.now()
        self.storage.save_rule(self._rule_to_dict(rule))
        return rule

    def get(self, rule_id: str) -> Optional[HealthRule]:
        """根据 ID 获取规则"""
        row = self.storage.get_rule(rule_id)
        return self._dict_to_rule(row) if row else None

    def list(self, enabled_only: bool = False) -> List[HealthRule]:
        """列出所有规则"""
        rows = self.storage.list_rules(enabled_only=enabled_only)
        return [self._dict_to_rule(r) for r in rows]

    def list_by_target_type(self, target_type_id: str) -> List[HealthRule]:
        """按 target_type_id 过滤规则"""
        rows = self.storage.list_rules_by_target_type(target_type_id)
        return [self._dict_to_rule(r) for r in rows]

    def list_by_severity(self, severity: HealthSeverity) -> List[HealthRule]:
        """按严重度过滤规则"""
        rows = self.storage.list_rules_by_severity(severity.value)
        return [self._dict_to_rule(r) for r in rows]

    def delete(self, rule_id: str) -> bool:
        """删除规则；返回是否成功"""
        return self.storage.delete_rule(rule_id)

    # ---------- 内部工具 ----------

    @staticmethod
    def _rule_to_dict(rule: HealthRule) -> dict:
        """将 HealthRule 转为持久化 dict"""
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
    def _dict_to_rule(row: dict) -> HealthRule:
        """将持久化 dict 还原为 HealthRule"""
        created = _parse_dt(row.get("created_at"))
        updated = _parse_dt(row.get("updated_at"))
        return HealthRule(
            id=row.get("id", ""),
            target_type_id=row.get("target_type_id", ""),
            name=row.get("name", ""),
            description=row.get("description", ""),
            rule_type=row.get("rule_type", "not_null"),
            check_expression=row.get("check_expression", {}) or {},
            severity=HealthSeverity(row.get("severity", "warning")),
            schedule=row.get("schedule", "") or "",
            notification_channel=row.get("notification_channel", {}) or {},
            enabled=bool(row.get("enabled", True)),
            created_at=created,
            updated_at=updated,
        )


def _parse_dt(value):
    """从 ISO 字符串解析 datetime；失败时回退到 now()"""
    if not value:
        return datetime.now()
    if isinstance(value, datetime):
        return value
    try:
        return datetime.fromisoformat(value)
    except (TypeError, ValueError):
        return datetime.now()
