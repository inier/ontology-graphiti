"""
Permission Checker 增强模块
基于 OPA 的细粒度权限校验，提供审计日志、策略模拟、权限级别管理

Phase 2 扩展: Permission Checker
"""

import json
import logging
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any, Dict, List, Optional

logger = logging.getLogger("permission_checker")


class PermissionLevel(str, Enum):
    """权限级别"""
    SYSTEM_ADMIN = "system_admin"
    PROJECT_OWNER = "project_owner"
    TEAM_LEADER = "team_leader"
    MEMBER = "member"
    GUEST = "guest"


class PermissionDecision(str, Enum):
    """权限决策结果"""
    ALLOWED = "allowed"
    DENIED = "denied"
    CONDITIONAL = "conditional"
    ERROR = "error"


@dataclass
class AuditLogEntry:
    """审计日志条目"""
    timestamp: str
    user_role: str
    action: str
    resource_id: str
    resource_type: str
    decision: str
    reason: str
    mode: str
    policy_version: str
    execution_time_ms: float


@dataclass
class PermissionContext:
    """权限检查上下文"""
    user_role: str
    action: str
    resource: Dict[str, Any]
    environment: Dict[str, Any] = field(default_factory=dict)
    time_constraints: Dict[str, Any] = field(default_factory=dict)
    additional_context: Dict[str, Any] = field(default_factory=dict)


@dataclass
class PermissionResult:
    """权限检查结果"""
    allowed: bool
    decision: PermissionDecision
    reason: str
    matched_policy: Optional[str] = None
    conditions: Optional[Dict[str, Any]] = None
    execution_time_ms: float = 0.0
    details: Optional[Dict[str, Any]] = None


class PermissionChecker:
    """
    Permission Checker - 增强版权限校验器

    功能：
    - 详细的权限决策结果
    - 审计日志记录
    - 策略模拟
    - 权限级别管理
    - 条件权限支持
    """

    _instance: Optional['PermissionChecker'] = None

    def __init__(self):
        from odap.infra.opa import OPAManager

        self.opa_manager = OPAManager()
        self.audit_logs: List[AuditLogEntry] = []
        self.permission_levels = self._init_permission_levels()

    @classmethod
    def get_instance(cls) -> 'PermissionChecker':
        if cls._instance is None:
            cls._instance = PermissionChecker()
        return cls._instance

    def _init_permission_levels(self) -> Dict[str, Dict[str, Any]]:
        """初始化权限级别配置"""
        return {
            PermissionLevel.SYSTEM_ADMIN.value: {
                "name": "系统管理员",
                "priority": 1,
                "permissions": ["*"],
                "restrictions": [],
            },
            PermissionLevel.PROJECT_OWNER.value: {
                "name": "项目所有者",
                "priority": 2,
                "permissions": ["read", "write", "delete"],
                "restrictions": ["system_config"],
            },
            PermissionLevel.TEAM_LEADER.value: {
                "name": "团队领导",
                "priority": 3,
                "permissions": ["read", "update"],
                "restrictions": ["delete", "system_config"],
            },
            PermissionLevel.MEMBER.value: {
                "name": "成员",
                "priority": 4,
                "permissions": ["read"],
                "restrictions": ["write", "delete", "system_config"],
            },
            PermissionLevel.GUEST.value: {
                "name": "访客",
                "priority": 5,
                "permissions": ["limited_read"],
                "restrictions": ["*"],
            },
        }

    def check_permission(
        self,
        user_role: str,
        action: str,
        resource: Dict[str, Any],
        context: Optional[PermissionContext] = None,
    ) -> PermissionResult:
        """检查权限并返回详细信息"""
        import time

        start_time = time.perf_counter()

        try:
            basic_result = self.opa_manager.check_permission(user_role, action, resource)

            resource_type = resource.get("type", "Unknown") if isinstance(resource, dict) else "Unknown"
            resource_id = resource.get("id", "unknown") if isinstance(resource, dict) else str(resource)

            reason = self._generate_reason(user_role, action, resource_type, basic_result)

            result = PermissionResult(
                allowed=basic_result,
                decision=PermissionDecision.ALLOWED if basic_result else PermissionDecision.DENIED,
                reason=reason,
                matched_policy=f"battlefield/allow",
                execution_time_ms=(time.perf_counter() - start_time) * 1000,
            )

            self._add_audit_log(
                user_role=user_role,
                action=action,
                resource_id=resource_id,
                resource_type=resource_type,
                decision=result.decision.value,
                reason=reason,
                execution_time_ms=result.execution_time_ms,
            )

            return result

        except Exception as e:
            logger.error(f"权限检查异常: {e}")
            return PermissionResult(
                allowed=False,
                decision=PermissionDecision.ERROR,
                reason=f"权限检查失败: {str(e)}",
                execution_time_ms=(time.perf_counter() - start_time) * 1000,
            )

    def check_permission_with_conditions(
        self,
        user_role: str,
        action: str,
        resource: Dict[str, Any],
        conditions: Dict[str, Any],
    ) -> PermissionResult:
        """检查带条件的权限"""
        result = self.check_permission(user_role, action, resource)

        if result.allowed and conditions:
            for key, expected_value in conditions.items():
                actual_value = resource.get(key)
                if actual_value != expected_value:
                    return PermissionResult(
                        allowed=False,
                        decision=PermissionDecision.CONDITIONAL,
                        reason=f"条件不满足: {key} 应该是 {expected_value}，实际是 {actual_value}",
                        conditions=conditions,
                        execution_time_ms=result.execution_time_ms,
                    )

        return result

    def simulate_permission(
        self,
        user_role: str,
        action: str,
        resource: Dict[str, Any],
        hypothetical_role: Optional[str] = None,
    ) -> Dict[str, Any]:
        """模拟权限检查（What-if 分析）"""
        test_role = hypothetical_role or user_role

        result = self.check_permission(test_role, action, resource)

        return {
            "test_role": test_role,
            "original_role": user_role,
            "action": action,
            "resource_id": resource.get("id", "unknown"),
            "decision": result.decision.value,
            "allowed": result.allowed,
            "reason": result.reason,
            "would_change": hypothetical_role is not None and hypothetical_role != user_role,
        }

    def batch_check_permissions(
        self,
        requests: List[Dict[str, Any]],
    ) -> List[PermissionResult]:
        """批量权限检查"""
        results = []
        for req in requests:
            result = self.check_permission(
                user_role=req.get("user_role", "guest"),
                action=req.get("action", "read"),
                resource=req.get("resource", {}),
            )
            results.append(result)
        return results

    def get_permission_summary(self, user_role: str) -> Dict[str, Any]:
        """获取用户权限摘要"""
        level_config = self.permission_levels.get(user_role, {})

        return {
            "user_role": user_role,
            "level_name": level_config.get("name", "未知"),
            "priority": level_config.get("priority", 999),
            "permissions": level_config.get("permissions", []),
            "restrictions": level_config.get("restrictions", []),
            "audit_log_count": len([log for log in self.audit_logs if log.user_role == user_role]),
        }

    def get_audit_logs(
        self,
        user_role: Optional[str] = None,
        action: Optional[str] = None,
        limit: int = 100,
    ) -> List[Dict[str, Any]]:
        """获取审计日志"""
        logs = self.audit_logs

        if user_role:
            logs = [log for log in logs if log.user_role == user_role]
        if action:
            logs = [log for log in logs if log.action == action]

        return [
            {
                "timestamp": log.timestamp,
                "user_role": log.user_role,
                "action": log.action,
                "resource_id": log.resource_id,
                "decision": log.decision,
                "reason": log.reason,
            }
            for log in logs[-limit:]
        ]

    def _add_audit_log(
        self,
        user_role: str,
        action: str,
        resource_id: str,
        resource_type: str,
        decision: str,
        reason: str,
        execution_time_ms: float,
    ):
        """添加审计日志"""
        entry = AuditLogEntry(
            timestamp=datetime.now().isoformat(),
            user_role=user_role,
            action=action,
            resource_id=resource_id,
            resource_type=resource_type,
            decision=decision,
            reason=reason,
            mode="opa" if not self.opa_manager.use_mock else "mock",
            policy_version=self.opa_manager.policy_versions.get("current", "unknown"),
            execution_time_ms=execution_time_ms,
        )
        self.audit_logs.append(entry)

        if len(self.audit_logs) > 10000:
            self.audit_logs = self.audit_logs[-5000:]

    def _generate_reason(
        self,
        user_role: str,
        action: str,
        resource_type: str,
        allowed: bool,
    ) -> str:
        """生成权限决策原因"""
        if allowed:
            return f"角色 {user_role} 允许执行 {action} 操作（资源类型: {resource_type}）"
        else:
            return f"角色 {user_role} 被拒绝执行 {action} 操作（资源类型: {resource_type}）"

    def get_statistics(self) -> Dict[str, Any]:
        """获取权限检查统计"""
        total = len(self.audit_logs)
        if total == 0:
            return {"total_checks": 0, "allowed_rate": 0.0}

        allowed_count = len([log for log in self.audit_logs if log.decision == "allowed"])

        by_role = {}
        for log in self.audit_logs:
            if log.user_role not in by_role:
                by_role[log.user_role] = {"total": 0, "allowed": 0}
            by_role[log.user_role]["total"] += 1
            if log.decision == "allowed":
                by_role[log.user_role]["allowed"] += 1

        return {
            "total_checks": total,
            "allowed_count": allowed_count,
            "denied_count": total - allowed_count,
            "allowed_rate": allowed_count / total if total > 0 else 0.0,
            "by_role": by_role,
            "mock_mode_count": len([log for log in self.audit_logs if log.mode == "mock"]),
        }


def create_permission_context(
    user_role: str,
    action: str,
    resource: Dict[str, Any],
    time_start: Optional[str] = None,
    time_end: Optional[str] = None,
    ip_restriction: Optional[str] = None,
) -> PermissionContext:
    """创建权限上下文"""
    environment = {}
    if ip_restriction:
        environment["ip_restriction"] = ip_restriction

    time_constraints = {}
    if time_start or time_end:
        time_constraints = {"start": time_start, "end": time_end}

    return PermissionContext(
        user_role=user_role,
        action=action,
        resource=resource,
        environment=environment,
        time_constraints=time_constraints,
    )