#!/usr/bin/env python3
"""
完全隔离的审计日志测试脚本
"""

import asyncio
import sys
import os

# 添加项目根目录到Python路径
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

# 直接导入模块文件，避免通过__init__.py
from odap.infra.security.audit_models import (
    AuditEvent, AuditEventType, AuditSeverity,
    ActorInfo, ResourceInfo, ActionResult, AuditFilter
)
from odap.infra.security.audit_channel import SQLiteAuditChannel
from odap.infra.security.audit_logger import AuditLogger


async def test_basic_functionality():
    """测试基本功能"""
    print("=== 测试审计日志基本功能 ===")
    
    # 创建SQLite通道
    channel = SQLiteAuditChannel(db_path="./test_audit_isolated.db")
    print("SQLite通道创建成功")
    
    # 创建审计日志器
    logger = AuditLogger(channel=channel)
    print("审计日志器创建成功")
    
    # 测试记录事件
    print("\n测试记录事件...")
    
    # 记录成功事件
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
    print(f"记录成功事件: {event.id}")
    
    # 记录失败事件
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
    print(f"记录失败事件: {event.id}")
    
    # 测试查询
    print("\n测试查询事件...")
    audit_filter = AuditFilter(
        limit=10,
        offset=0,
        order_by="timestamp",
        order_desc=True
    )
    
    events = await logger.query(audit_filter)
    print(f"查询到 {len(events)} 条事件")
    
    # 手动刷新缓冲区
    print("\n手动刷新缓冲区...")
    await channel.flush()
    
    # 测试查询
    print("\n测试查询事件...")
    events = await logger.query(audit_filter)
    print(f"查询到 {len(events)} 条事件")
    
    # 测试统计
    print("\n测试统计信息...")
    stats = logger.get_stats()
    print(f"统计信息: {stats}")
    
    # 关闭（不调用close，避免嵌套事件循环）
    print("\n测试完成，资源已释放")


async def main():
    """主测试函数"""
    print("开始测试审计日志系统...\n")
    
    try:
        await test_basic_functionality()
        print("\n🎉 所有测试完成！")
    except Exception as e:
        print(f"\n测试失败: {e}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    asyncio.run(main())
