#!/usr/bin/env python3
"""
重构后的审计日志测试脚本
"""

import asyncio
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from odap.infra.security.audit_models import (
    AuditEvent, AuditEventType, AuditSeverity,
    ActorInfo, ResourceInfo, ActionResult, AuditFilter
)
from odap.infra.security.audit_sqlite_channel import SQLiteAuditChannel
from odap.infra.security.audit_logger import AuditLogger


async def test_refactored_architecture():
    """测试重构后的架构"""
    print("=== 测试重构后的审计日志架构 ===\n")

    # 创建SQLite通道
    channel = SQLiteAuditChannel(db_path="./test_refactored.db")
    print("1. SQLite通道创建成功")

    # 创建审计日志器（同时支持SQLite和Graphiti）
    logger = AuditLogger(channel=channel, enable_graphiti=False)
    print("2. 统一日志器创建成功（Graphiti已禁用以便测试）")

    # 测试记录事件
    print("\n3. 测试记录事件...")
    event = await logger.log_success(
        event_type=AuditEventType.USER_LOGIN,
        action="user_login",
        resource=ResourceInfo(
            resource_type="auth",
            resource_id="login",
            resource_name="Login"
        ),
        message="User logged in successfully"
    )
    print(f"   记录成功事件: {event.id}")

    event = await logger.log_failure(
        event_type=AuditEventType.USER_LOGIN,
        action="user_login",
        resource=ResourceInfo(
            resource_type="auth",
            resource_id="login",
            resource_name="Login"
        ),
        message="Invalid credentials",
        error_code="401"
    )
    print(f"   记录失败事件: {event.id}")

    # 刷新缓冲区
    await channel.flush()
    print("\n4. 缓冲区刷新成功")

    # 测试查询
    print("\n5. 测试查询事件...")
    audit_filter = AuditFilter(
        limit=10,
        offset=0,
        order_by="timestamp",
        order_desc=True
    )
    events = await logger.query(audit_filter)
    print(f"   查询到 {len(events)} 条事件")

    # 测试统计
    print("\n6. 测试统计信息...")
    stats = logger.get_stats()
    print(f"   统计信息: {stats}")

    # 测试便捷方法
    print("\n7. 测试便捷方法...")
    event = await logger.log_denied(
        event_type=AuditEventType.USER_LOGIN,
        action="user_login",
        resource=ResourceInfo(
            resource_type="auth",
            resource_id="login",
            resource_name="Login"
        ),
        message="Access denied"
    )
    print(f"   记录拒绝事件: {event.id}")

    await channel.flush()
    print("\n=== 测试完成 ===")


async def main():
    """主测试函数"""
    try:
        await test_refactored_architecture()
        print("\n🎉 重构后的审计日志架构测试通过！")
    except Exception as e:
        print(f"\n测试失败: {e}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    asyncio.run(main())
