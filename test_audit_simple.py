#!/usr/bin/env python3
"""
简化的审计日志测试脚本
"""

import asyncio
import sys
import os

# 添加项目根目录到Python路径
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

# 直接导入审计相关模块，避免依赖问题
from odap.infra.security.audit_models import (
    AuditEvent, AuditEventType, AuditSeverity,
    ActorInfo, ResourceInfo, ActionResult, AuditFilter
)
from odap.infra.security.audit_channel import SQLiteAuditChannel
from odap.infra.security.audit_logger import AuditLogger


async def test_basic_logging():
    """测试基本日志记录"""
    print("=== 测试基本日志记录 ===")
    
    # 创建通道和日志器
    channel = SQLiteAuditChannel(db_path="./test_audit.db")
    logger = AuditLogger(channel=channel)
    
    # 测试成功事件
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
    
    # 测试失败事件
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
    
    print("基本日志记录测试完成\n")
    return logger


async def test_query_logs(logger):
    """测试查询日志"""
    print("=== 测试查询日志 ===")
    
    # 构建过滤器
    audit_filter = AuditFilter(
        limit=10,
        offset=0,
        order_by="timestamp",
        order_desc=True
    )
    
    # 查询事件
    events = await logger.query(audit_filter)
    print(f"查询到 {len(events)} 条事件")
    
    # 打印前3条事件
    for i, event in enumerate(events[:3]):
        print(f"事件 {i+1}: {event.event_type.value} - {event.action} - {event.result.status}")
    
    print("查询日志测试完成\n")


async def test_stats(logger):
    """测试统计信息"""
    print("=== 测试统计信息 ===")
    
    # 获取统计信息
    stats = logger.get_stats()
    print(f"统计信息: {stats}")
    
    print("统计信息测试完成\n")


async def main():
    """主测试函数"""
    print("开始测试审计日志系统...\n")
    
    try:
        logger = await test_basic_logging()
        await test_query_logs(logger)
        await test_stats(logger)
        
        print("🎉 所有测试完成！")
    finally:
        # 关闭审计日志器
        if 'logger' in locals():
            logger.close()
        print("审计日志器已关闭")


if __name__ == "__main__":
    asyncio.run(main())
