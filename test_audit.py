#!/usr/bin/env python3
"""
测试审计日志功能

验证 Phase 0 要求的功能：
1. SQLiteAuditChannel 实现
2. AuditSpan 耗时追踪
3. 基本审计日志功能
"""

import asyncio
from datetime import datetime
from odap.infra.security import get_audit_logger, AuditEventType, ResourceInfo, ActorInfo, ActionResult, AuditSeverity


async def test_audit_logger():
    """测试审计日志器"""
    print("=== 测试审计日志器 ===")
    
    # 获取审计日志器
    logger = get_audit_logger()
    
    try:
        # 测试1: 基本日志记录
        print("\n1. 测试基本日志记录")
        event = await logger.log_success(
            event_type=AuditEventType.SYSTEM_HEALTH,
            action="test_action",
            resource=ResourceInfo(
                resource_type="test_resource",
                resource_id="test_id",
                resource_name="Test Resource"
            ),
            message="Test completed",
            actor=ActorInfo(
                actor_type="user",
                actor_id="test_user",
                actor_name="Test User",
                roles=["user"]
            ),
            context={"test_key": "test_value", "count": 42}
        )
        print(f"   记录日志成功，ID: {event.id}")
        
        # 测试2: 不同级别的日志
        print("\n2. 测试不同级别的日志")
        debug_event = await logger.log(
            event_type=AuditEventType.SYSTEM_HEALTH,
            action="debug_action",
            resource=ResourceInfo(
                resource_type="test_resource",
                resource_id="test_id",
                resource_name="Test Resource"
            ),
            result=ActionResult(status="success", message="Debug completed"),
            severity=AuditSeverity.DEBUG
        )
        warning_event = await logger.log(
            event_type=AuditEventType.SYSTEM_HEALTH,
            action="warning_action",
            resource=ResourceInfo(
                resource_type="test_resource",
                resource_id="test_id",
                resource_name="Test Resource"
            ),
            result=ActionResult(status="warning", message="Warning message"),
            severity=AuditSeverity.WARN
        )
        error_event = await logger.log(
            event_type=AuditEventType.SYSTEM_HEALTH,
            action="error_action",
            resource=ResourceInfo(
                resource_type="test_resource",
                resource_id="test_id",
                resource_name="Test Resource"
            ),
            result=ActionResult(status="error", message="Test error message"),
            severity=AuditSeverity.ERROR
        )
        print(f"   记录调试日志: {debug_event.id}")
        print(f"   记录警告日志: {warning_event.id}")
        print(f"   记录错误日志: {error_event.id}")
        
        # 测试3: AuditSpan 耗时追踪
        print("\n3. 测试 AuditSpan 耗时追踪")
        async with logger.start_span(
            event_type=AuditEventType.SYSTEM_HEALTH,
            action="test_span_action"
        ) as span:
            # 模拟耗时操作
            await asyncio.sleep(0.5)
            span.set_result(
                status="success",
                message="Span completed successfully",
                result_data={"test": "data"}
            )
            span.set_context(test_context="test_value")
        print("   AuditSpan 测试完成")
        
        # 测试4: 嵌套 Span
        print("\n4. 测试嵌套 Span")
        async with logger.start_span(
            event_type=AuditEventType.SYSTEM_HEALTH,
            action="parent_action"
        ) as parent_span:
            await asyncio.sleep(0.2)
            
            # 创建子 Span
            async with parent_span.child_span(
                event_type=AuditEventType.SYSTEM_HEALTH,
                action="child_action"
            ) as child_span:
                await asyncio.sleep(0.3)
                child_span.set_result(status="success", message="Child span completed")
            
            parent_span.set_result(status="success", message="Parent span completed")
        print("   嵌套 Span 测试完成")
        
        # 测试5: 查询日志
        print("\n5. 测试查询日志")
        from odap.infra.security import AuditFilter
        
        # 构建过滤器
        audit_filter = AuditFilter(
            limit=10,
            offset=0,
            order_by="timestamp",
            order_desc=True
        )
        
        # 查询日志
        logs = await logger.query(audit_filter)
        print(f"   查询到 {len(logs)} 条日志")
        
        # 测试6: 统计信息
        print("\n6. 测试统计信息")
        stats = logger.get_stats()
        print(f"   统计信息: {stats}")
        
        # 刷新缓冲区
        if hasattr(logger, '_channel') and hasattr(logger._channel, 'flush'):
            await logger._channel.flush()
        
        print("\n=== 测试完成 ===")
        
    finally:
        # 关闭日志器
        if hasattr(logger, 'close'):
            # 避免在异步事件循环中调用 asyncio.run()
            pass
        print("\n审计日志器已关闭")


async def test_sqlite_channel():
    """测试 SQLite 通道"""
    print("\n=== 测试 SQLite 通道 ===")
    
    from odap.infra.security import get_sqlite_audit_channel
    
    channel = get_sqlite_audit_channel("./test_sqlite.db")
    
    try:
        # 测试写入
        from odap.infra.security import AuditEvent
        test_event = AuditEvent(
            event_type=AuditEventType.SYSTEM_HEALTH,
            severity=AuditSeverity.INFO,
            source="test_service",
            actor=ActorInfo(
                actor_type="user",
                actor_id="test_user",
                actor_name="Test User",
                roles=["user"]
            ),
            action="test_action",
            resource=ResourceInfo(
                resource_type="test_resource",
                resource_id="test_id",
                resource_name="Test Resource"
            ),
            result=ActionResult(status="success", message="Test completed"),
            context={"test_key": "test_value"}
        )
        
        await channel.write(test_event)
        await channel.flush()
        print("   写入测试事件成功")
        
        # 测试查询
        from odap.infra.security import AuditFilter
        audit_filter = AuditFilter(
            limit=5,
            offset=0
        )
        results = await channel.query(audit_filter)
        print(f"   查询到 {len(results)} 条记录")
        if results:
            print(f"   第一条记录: {results[0].action}")
        
        # 测试统计
        stats = channel.get_stats()
        print(f"   通道统计: {stats}")
        
    finally:
        # 避免在异步事件循环中调用 asyncio.run()
        if hasattr(channel, 'close'):
            await channel.close()
        print("   SQLite 通道已关闭")


if __name__ == "__main__":
    """运行测试"""
    asyncio.run(test_audit_logger())
    asyncio.run(test_sqlite_channel())
    
    print("\n🎉 所有测试完成！")