"""
PermissionChecker 测试用例
"""

import sys
import os
import asyncio

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from core.permission_checker import (
    PermissionChecker,
    PermissionLevel,
    PermissionDecision,
    AuditLogEntry,
    PermissionContext,
    PermissionResult,
    create_permission_context,
)


def test_permission_level_enum():
    """测试权限级别枚举"""
    print("=== 测试 PermissionLevel 枚举 ===")
    assert PermissionLevel.SYSTEM_ADMIN.value == "system_admin"
    assert PermissionLevel.PROJECT_OWNER.value == "project_owner"
    assert PermissionLevel.TEAM_LEADER.value == "team_leader"
    assert PermissionLevel.MEMBER.value == "member"
    assert PermissionLevel.GUEST.value == "guest"
    print("PermissionLevel 枚举测试通过")
    return True


def test_permission_decision_enum():
    """测试权限决策枚举"""
    print("\n=== 测试 PermissionDecision 枚举 ===")
    assert PermissionDecision.ALLOWED.value == "allowed"
    assert PermissionDecision.DENIED.value == "denied"
    assert PermissionDecision.CONDITIONAL.value == "conditional"
    assert PermissionDecision.ERROR.value == "error"
    print("PermissionDecision 枚举测试通过")
    return True


def test_permission_context():
    """测试 PermissionContext"""
    print("\n=== 测试 PermissionContext ===")
    context = PermissionContext(
        user_role="commander",
        action="attack",
        resource={"id": "WEAPON_1", "type": "WeaponSystem"},
        environment={"ip_restriction": "192.168.1.0/24"},
    )
    assert context.user_role == "commander"
    assert context.action == "attack"
    assert context.resource["id"] == "WEAPON_1"
    assert context.environment["ip_restriction"] == "192.168.1.0/24"
    print("PermissionContext 测试通过")
    return True


def test_permission_result():
    """测试 PermissionResult"""
    print("\n=== 测试 PermissionResult ===")
    result = PermissionResult(
        allowed=True,
        decision=PermissionDecision.ALLOWED,
        reason="测试原因",
        matched_policy="test_policy",
        execution_time_ms=5.5,
    )
    assert result.allowed == True
    assert result.decision == PermissionDecision.ALLOWED
    assert result.execution_time_ms == 5.5
    print("PermissionResult 测试通过")
    return True


def test_permission_checker_singleton():
    """测试 PermissionChecker 单例"""
    print("\n=== 测试 PermissionChecker 单例 ===")
    checker1 = PermissionChecker.get_instance()
    checker2 = PermissionChecker.get_instance()
    assert checker1 is checker2
    print("PermissionChecker 单例测试通过")
    return True


def test_check_permission():
    """测试权限检查"""
    print("\n=== 测试权限检查 ===")
    checker = PermissionChecker.get_instance()

    result = checker.check_permission(
        user_role="commander",
        action="attack",
        resource={"id": "WEAPON_1", "type": "WeaponSystem", "properties": {"type": "雷达"}},
    )
    assert isinstance(result, PermissionResult)
    assert result.allowed == True
    assert result.decision == PermissionDecision.ALLOWED
    print(f"  权限检查结果: {result.decision.value} - {result.reason}")
    print("权限检查测试通过")
    return True


def test_check_permission_denied():
    """测试权限拒绝"""
    print("\n=== 测试权限拒绝 ===")
    checker = PermissionChecker.get_instance()

    result = checker.check_permission(
        user_role="pilot",
        action="attack",
        resource={"id": "WEAPON_1", "type": "WeaponSystem", "properties": {"type": "雷达"}},
    )
    assert result.allowed == False
    assert result.decision == PermissionDecision.DENIED
    print(f"  权限拒绝结果: {result.decision.value} - {result.reason}")
    print("权限拒绝测试通过")
    return True


def test_check_permission_with_conditions():
    """测试带条件权限检查"""
    print("\n=== 测试带条件权限检查 ===")
    checker = PermissionChecker.get_instance()

    result = checker.check_permission_with_conditions(
        user_role="commander",
        action="attack",
        resource={"id": "WEAPON_1", "type": "WeaponSystem", "zone": "B"},
        conditions={"zone": "B"},
    )
    assert result.allowed == True

    result2 = checker.check_permission_with_conditions(
        user_role="commander",
        action="attack",
        resource={"id": "WEAPON_1", "type": "WeaponSystem", "zone": "A"},
        conditions={"zone": "B"},
    )
    assert result2.allowed == False
    assert result2.decision == PermissionDecision.CONDITIONAL
    print("带条件权限检查测试通过")
    return True


def test_simulate_permission():
    """测试权限模拟"""
    print("\n=== 测试权限模拟 ===")
    checker = PermissionChecker.get_instance()

    result = checker.simulate_permission(
        user_role="pilot",
        action="attack",
        resource={"id": "WEAPON_1", "type": "WeaponSystem", "properties": {"type": "雷达"}},
        hypothetical_role="commander",
    )
    assert result["test_role"] == "commander"
    assert result["original_role"] == "pilot"
    assert result["allowed"] == True
    assert result["would_change"] == True
    print(f"  模拟结果: {result['test_role']} vs {result['original_role']} = {result['allowed']}")
    print("权限模拟测试通过")
    return True


def test_batch_check_permissions():
    """测试批量权限检查"""
    print("\n=== 测试批量权限检查 ===")
    checker = PermissionChecker.get_instance()

    requests = [
        {"user_role": "commander", "action": "attack", "resource": {"id": "W1", "type": "Weapon"}},
        {"user_role": "pilot", "action": "attack", "resource": {"id": "W1", "type": "Weapon"}},
        {"user_role": "pilot", "action": "view_intelligence", "resource": {"id": "I1", "type": "Intel"}},
    ]

    results = checker.batch_check_permissions(requests)
    assert len(results) == 3
    assert results[0].allowed == True
    assert results[1].allowed == False
    assert results[2].allowed == True
    print(f"  批量检查结果: 允许 {sum(1 for r in results if r.allowed)}/{len(results)}")
    print("批量权限检查测试通过")
    return True


def test_get_permission_summary():
    """测试获取权限摘要"""
    print("\n=== 测试获取权限摘要 ===")
    checker = PermissionChecker.get_instance()

    summary = checker.get_permission_summary("commander")
    assert summary["user_role"] == "commander"
    assert "permissions" in summary
    assert "restrictions" in summary
    print(f"  角色: {summary['user_role']}, 权限数: {len(summary['permissions'])}")
    print("权限摘要测试通过")
    return True


def test_get_audit_logs():
    """测试获取审计日志"""
    print("\n=== 测试获取审计日志 ===")
    checker = PermissionChecker.get_instance()

    checker.check_permission(
        user_role="commander",
        action="attack",
        resource={"id": "W1", "type": "WeaponSystem"},
    )

    logs = checker.get_audit_logs(user_role="commander", limit=10)
    assert len(logs) >= 1
    print(f"  审计日志数: {len(logs)}")
    print("审计日志测试通过")
    return True


def test_get_statistics():
    """测试获取统计信息"""
    print("\n=== 测试获取统计信息 ===")
    checker = PermissionChecker.get_instance()

    checker.check_permission(
        user_role="commander",
        action="attack",
        resource={"id": "W1", "type": "WeaponSystem"},
    )
    checker.check_permission(
        user_role="pilot",
        action="view_intelligence",
        resource={"id": "I1", "type": "Intel"},
    )

    stats = checker.get_statistics()
    assert stats["total_checks"] >= 2
    assert "allowed_rate" in stats
    assert "by_role" in stats
    print(f"  总检查数: {stats['total_checks']}, 允许率: {stats['allowed_rate']:.2%}")
    print("统计信息测试通过")
    return True


def test_create_permission_context():
    """测试创建权限上下文"""
    print("\n=== 测试创建权限上下文 ===")
    context = create_permission_context(
        user_role="commander",
        action="attack",
        resource={"id": "W1", "type": "WeaponSystem"},
        time_start="2024-01-01T00:00:00",
        time_end="2024-12-31T23:59:59",
        ip_restriction="10.0.0.0/8",
    )
    assert context.user_role == "commander"
    assert context.time_constraints["start"] == "2024-01-01T00:00:00"
    assert context.environment["ip_restriction"] == "10.0.0.0/8"
    print("创建权限上下文测试通过")
    return True


def run_all_tests():
    """运行所有测试"""
    print("=" * 60)
    print("开始运行 PermissionChecker 测试...")
    print("=" * 60)

    tests = [
        test_permission_level_enum,
        test_permission_decision_enum,
        test_permission_context,
        test_permission_result,
        test_permission_checker_singleton,
        test_check_permission,
        test_check_permission_denied,
        test_check_permission_with_conditions,
        test_simulate_permission,
        test_batch_check_permissions,
        test_get_permission_summary,
        test_get_audit_logs,
        test_get_statistics,
        test_create_permission_context,
    ]

    passed = 0
    failed = 0

    for test in tests:
        try:
            if test():
                passed += 1
            else:
                failed += 1
                print(f"  ❌ {test.__name__} 返回 False")
        except Exception as e:
            failed += 1
            print(f"  ❌ {test.__name__}: {e}")

    print("\n" + "=" * 60)
    print(f"测试结果: 成功 {passed}, 失败 {failed}")
    print("=" * 60)

    if failed == 0:
        print("🎉 所有测试通过！")
    else:
        print("❌ 有测试失败，请检查代码")

    return failed == 0


if __name__ == "__main__":
    run_all_tests()