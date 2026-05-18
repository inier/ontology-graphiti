#!/usr/bin/env python3
"""
测试 OPA 策略管理 v2 新功能
"""

import sys
import os
from datetime import datetime

# 添加项目路径
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from odap.infra.opa.opa_service import OPAManager


def test_abac_permission():
    """测试ABAC策略"""
    print("\n=== 测试 ABAC 策略 ===")
    manager = OPAManager()
    
    # 测试ABAC权限检查
    user = {
        "id": "user1",
        "roles": ["commander"],
        "attributes": {
            "authenticated": True,
            "security_level": 3
        }
    }
    
    resource = {
        "id": "RADAR_01",
        "type": "WeaponSystem",
        "attributes": {
            "status": "available",
            "confidentiality_level": 2
        }
    }
    
    environment = {
        "time_of_day": "10:00",
        "network_type": "internal"
    }
    
    result = manager.check_permission_abac(user, "attack", resource, environment)
    print(f"ABAC 权限检查结果: {result}")


def test_batch_permission():
    """测试批量权限检查"""
    print("\n=== 测试 批量权限检查 ===")
    manager = OPAManager()
    
    # 测试批量权限检查
    requests = [
        {
            "user_role": "commander",
            "action": "attack",
            "resource": {
                "id": "RADAR_01",
                "type": "WeaponSystem"
            }
        },
        {
            "user_role": "pilot",
            "action": "attack",
            "resource": {
                "id": "RADAR_01",
                "type": "WeaponSystem"
            }
        }
    ]
    
    results = manager.check_permissions_batch(requests)
    print(f"批量权限检查结果: {results}")


def test_cache_performance():
    """测试缓存性能"""
    print("\n=== 测试 缓存性能 ===")
    manager = OPAManager()
    
    # 执行多次相同的权限检查，测试缓存命中
    resource = {
        "id": "RADAR_01",
        "type": "WeaponSystem"
    }
    
    print("第一次权限检查（缓存未命中）:")
    result1 = manager.check_permission("commander", "attack", resource)
    print(f"结果: {result1}")
    
    print("\n第二次权限检查（缓存命中）:")
    result2 = manager.check_permission("commander", "attack", resource)
    print(f"结果: {result2}")
    
    # 获取缓存统计信息
    cache_stats = manager.get_cache_stats()
    print("\n缓存统计信息:")
    print(f"命中率: {cache_stats['hit_rate_percent']:.2f}%")
    print(f"缓存大小: {cache_stats['cache_size']}/{cache_stats['max_size']}")


def test_bundle_update():
    """测试Bundle热更新"""
    print("\n=== 测试 Bundle 热更新 ===")
    manager = OPAManager()
    
    # 获取当前Bundle版本
    current_version = manager.get_bundle_version()
    print(f"当前 Bundle 版本: {current_version}")
    
    # 更新Bundle
    new_version = manager.update_bundle()
    print(f"新 Bundle 版本: {new_version}")
    
    # 验证版本是否更新
    if new_version != current_version:
        print("Bundle 热更新成功!")
    else:
        print("Bundle 热更新失败!")


def test_performance_metrics():
    """测试性能指标"""
    print("\n=== 测试 性能指标 ===")
    manager = OPAManager()
    
    # 执行一些操作以生成指标
    for i in range(5):
        resource = {
            "id": f"RADAR_{i}",
            "type": "WeaponSystem"
        }
        manager.check_permission("commander", "attack", resource)
    
    # 获取性能指标
    metrics = manager.get_performance_metrics()
    print("性能指标:")
    print(f"模式: {metrics['mode']}")
    print(f"Bundle 版本: {metrics['bundle_version']}")
    print(f"缓存命中率: {metrics['cache']['hit_rate_percent']:.2f}%")
    print(f"历史记录数: {metrics['history_count']}")


def test_policy_sandbox():
    """测试策略沙箱"""
    print("\n=== 测试 策略沙箱 ===")
    manager = OPAManager()
    
    # 测试策略沙箱
    test_policy = """
    package domain
    
    default allow = false
    
    allow {
        input.user_role == "commander"
        input.action == "attack"
    }
    """
    
    result = manager.policy_sandbox(test_policy)
    print(f"策略沙箱执行结果: {result}")


if __name__ == "__main__":
    print("开始测试 OPA 策略管理 v2 新功能...")
    
    try:
        test_abac_permission()
        test_batch_permission()
        test_cache_performance()
        test_bundle_update()
        test_performance_metrics()
        test_policy_sandbox()
        print("\n测试完成!")
    except Exception as e:
        print(f"测试过程中发生错误: {e}")
        import traceback
        traceback.print_exc()
