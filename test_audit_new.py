#!/usr/bin/env python3
"""
测试新的审计日志系统
"""

import asyncio
from odap.infra.security import (
    get_audit_logger, AuditEventType, AuditSeverity,
    ActorInfo, ResourceInfo, ActionResult, AuditFilter
)


async def test_basic_logging():
    """测试基本日志记录"""
    print("=== 测试基本日志记录 ===")
    
    audit_logger = get_audit_logger()
    
    # 测试成功事件
    event = await audit_logger.log_success(
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
    event = await audit_logger.log_failure(
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
    
    # 测试拒绝事件
    event = await audit_logger.log_denied(
        event_type=AuditEventType.USER_LOGIN,
        action="user_login",
        resource=ResourceInfo(
            resource_type="auth",
            resource_id="login",
            resource_name="Login"
        ),
        message="Access denied"
    )
    print(f"记录拒绝事件: {event.id}")
    
    print("基本日志记录测试完成\n")


async def test_audit_span():
    """测试 AuditSpan 耗时追踪"""
    print("=== 测试 AuditSpan 耗时追踪 ===")
    
    audit_logger = get_audit_logger()
    
    # 测试基本 Span
    async with audit_logger.start_span(AuditEventType.AGENT_EXECUTE, "test_span") as span:
        # 模拟耗时操作
        await asyncio.sleep(0.1)
        span.set_result(status="success", message="Span completed")
    print("基本 Span 测试完成")
    
    # 测试嵌套 Span
    async with audit_logger.start_span(AuditEventType.AGENT_EXECUTE, "parent_span") as parent_span:
        await asyncio.sleep(0.05)
        
        # 创建子 Span
        async with parent_span.child_span(AuditEventType.AGENT_DECISION, "child_span") as child_span:
            await asyncio.sleep(0.05)
            child_span.set_result(status="success", message="Child span completed")
        
        parent_span.set_result(status="success", message="Parent span completed")
    print("嵌套 Span 测试完成\n")


async def test_query_logs():
    """测试查询日志"""
    print("=== 测试查询日志 ===")
    
    audit_logger = get_audit_logger()
    
    # 构建过滤器
    audit_filter = AuditFilter(
        limit=10,
        offset=0,
        order_by="timestamp",
        order_desc=True
    )
    
    # 查询事件
    events = await audit_logger.query(audit_filter)
    print(f"查询到 {len(events)} 条事件")
    
    # 打印前3条事件
    for i, event in enumerate(events[:3]):
        print(f"事件 {i+1}: {event.event_type.value} - {event.action} - {event.result.status}")
    
    print("查询日志测试完成\n")


async def test_stats():
    """测试统计信息"""
    print("=== 测试统计信息 ===")
    
    audit_logger = get_audit_logger()
    
    # 获取统计信息
    stats = audit_logger.get_stats()
    print(f"统计信息: {stats}")
    
    print("统计信息测试完成\n")


async def test_batch_logging():
    """测试批量日志记录"""
    print("=== 测试批量日志记录 ===")
    
    audit_logger = get_audit_logger()
    
    # 构建批量事件
    events = []
    for i in range(5):
        event = await audit_logger.log(
            event_type=AuditEventType.SYSTEM_HEALTH,
            action=f"test_batch_{i}",
            resource=ResourceInfo(
                resource_type="test",
                resource_id=f"test_{i}",
                resource_name=f"Test {i}"
            ),
            result=ActionResult(
                status="success",
                message=f"Test {i} completed"
            )
        )
        events.append(event)
    
    # 批量记录
    await audit_logger.log_batch(events)
    print(f"批量记录了 {len(events)} 条事件")
    
    print("批量日志记录测试完成\n")


async def main():
    """主测试函数"""
    print("开始测试审计日志系统...\n")
    
    try:
        await test_basic_logging()
        await test_audit_span()
        await test_query_logs()
        await test_stats()
        await test_batch_logging()
        
        print("🎉 所有测试完成！")
    finally:
        # 关闭审计日志器
        audit_logger = get_audit_logger()
        audit_logger.close()
        print("审计日志器已关闭")


if __name__ == "__main__":
    asyncio.run(main())
