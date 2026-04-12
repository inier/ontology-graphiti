# ADR-027: 采用Hook系统作为可扩展性核心架构

## 状态

**已接受** | **创建日期**: 2026-04-13 | **最后更新**: 2026-04-13

## 上下文

Graphiti作为战场仿真AI Agent平台，需要支持多种横切关注点（cross-cutting concerns）：
1. **权限控制**: 在工具调用前进行细粒度权限校验
2. **审计日志**: 记录所有关键操作的完整审计轨迹
3. **性能监控**: 收集系统性能指标，识别性能瓶颈
4. **数据缓存**: 智能缓存热点数据，提升系统响应速度
5. **错误处理**: 统一的错误处理和恢复机制
6. **业务扩展**: 在不修改核心代码的情况下添加新功能

当前系统面临以下挑战：
- **代码重复**: 每个关注点都在多个地方重复实现
- **维护困难**: 横切逻辑分散在代码各处，难以统一维护
- **扩展性差**: 新增关注点需要修改大量现有代码
- **测试复杂**: 横切逻辑与业务逻辑耦合，测试困难

现有解决方案包括：
1. **装饰器模式**: 在函数/方法级别添加额外行为
2. **中间件**: 在请求处理链中插入处理逻辑
3. **AOP框架**: 使用面向切面编程框架（如AspectJ）
4. **事件驱动**: 通过事件系统触发横切逻辑

但这些方案在AI Agent工具调用场景下存在局限性。

## 决策

**采用Hook系统作为Graphiti系统的可扩展性核心架构，基于OpenHarness的Hook机制实现统一的横切关注点管理。**

### 核心决策点：
1. **统一Hook接口**: 定义标准的Hook接口和生命周期
2. **事件驱动架构**: 基于事件类型触发Hook执行
3. **优先级管理**: 支持Hook执行的优先级控制
4. **依赖解析**: 自动处理Hook之间的依赖关系
5. **安全沙箱**: 提供Hook代码的安全执行环境

## 替代方案分析

### 方案A: 装饰器模式（当前状态）
- **优点**: 
  - 简单直接，易于理解
  - 类型安全，编译时检查
  - 与Python语言特性良好集成
- **缺点**:
  - 静态绑定，难以动态修改
  - 装饰器链过长时难以维护
  - 不支持运行时Hook注册/注销

### 方案B: 中间件模式
- **优点**:
  - 请求处理管道清晰
  - 支持动态添加/移除中间件
  - 适合HTTP/RPC请求处理
- **缺点**:
  - 不适合细粒度的工具调用拦截
  - 难以处理复杂的依赖关系
  - 与AI Agent工具调用模型不匹配

### 方案C: AOP框架（如AspectJ）
- **优点**:
  - 强大的横切关注点分离能力
  - 支持编译时和运行时织入
  - 成熟的生态系统
- **缺点**:
  - 学习曲线陡峭
  - 与Python生态系统集成复杂
  - 运行时性能开销较大

### 方案D: 事件驱动架构
- **优点**:
  - 高度解耦，扩展性强
  - 支持异步处理
  - 适合分布式系统
- **缺点**:
  - 事件处理顺序难以控制
  - 调试和跟踪困难
  - 不适合需要严格顺序的场景

### 方案E: Hook系统（最终选择）
- **优点**:
  - **专门为AI Agent设计**: 基于OpenHarness Hook机制
  - **细粒度控制**: 支持工具调用前/后、错误、超时等事件
  - **动态扩展**: 支持运行时Hook注册和配置
  - **优先级管理**: 明确的执行顺序控制
  - **安全可靠**: 内置沙箱执行和错误隔离
- **缺点**:
  - 需要设计完整的Hook生命周期管理
  - 增加了系统的复杂性
  - 需要额外的监控和调试工具

## 影响

### 正面影响
1. **提高代码可维护性**: 横切关注点集中管理
2. **增强系统可扩展性**: 支持动态添加新功能
3. **改善开发体验**: 统一的Hook开发接口
4. **提升系统稳定性**: 错误隔离和恢复机制
5. **加强安全性**: 统一的权限控制和审计

### 负面影响
1. **系统复杂性增加**: 需要管理Hook生命周期和依赖
2. **性能开销**: Hook执行增加额外延迟
3. **调试难度**: Hook调用链可能复杂
4. **学习成本**: 开发人员需要理解Hook系统

## 详细设计

### 架构设计
```
┌─────────────────────────────────────────────────────────┐
│                  Hook系统架构 (Hook System)                │
├─────────────────────────────────────────────────────────┤
│                                                           │
│  ┌─────────────────────────────────────────────────┐   │
│  │                Hook注册表 (Hook Registry)          │   │
│  │  • 注册/注销 Hook                                │   │
│  │  • 优先级管理                                    │   │
│  │  • 依赖解析                                      │   │
│  └─────────────────────────────────────────────────┘   │
│                                                           │
│         ┌─────────────────────────────────────────┐     │
│         │            Hook分发器 (Hook Dispatcher)    │     │
│         │  • 事件监听                              │     │
│         │  • Hook查找                              │     │
│         │  • 执行顺序控制                          │     │
│         └─────────────────────────────────────────┘     │
│                                                           │
│         ┌─────────────────────────────────────────┐     │
│         │            Hook执行器 (Hook Executor)      │     │
│         │  • 同步/异步执行                         │     │
│         │  • 超时控制                              │     │
│         │  • 错误处理                              │     │
│         └─────────────────────────────────────────┘     │
│                                                           │
│         ┌─────────────────────────────────────────┐     │
│         │            Hook监控器 (Hook Monitor)       │     │
│         │  • 性能监控                              │     │
│         │  • 使用统计                              │     │
│         │  • 健康检查                              │     │
│         └─────────────────────────────────────────┘     │
│                                                           │
│  ┌─────────────────────────────────────────────────┐   │
│  │                   Hook插件 (Hook Plugins)         │   │
│  │  ┌────────────┐ ┌────────────┐ ┌────────────┐ │   │
│  │  │  权限Hook  │ │  日志Hook  │ │ 监控Hook   │ │   │
│  │  │ (OPA集成)  │ │ (结构化日志) │ │(性能指标)  │ │   │
│  │  └────────────┘ └────────────┘ └────────────┘ │   │
│  └─────────────────────────────────────────────────┘   │
└─────────────────────────────────────────────────────────┘
```

### 核心组件
1. **Hook Registry**: 管理所有Hook的注册信息
2. **Hook Dispatcher**: 根据事件类型分发Hook执行
3. **Hook Executor**: 执行具体的Hook逻辑
4. **Hook Monitor**: 监控Hook执行状态和性能
5. **Hook Plugins**: 预定义的核心Hook插件

### Hook生命周期事件
```python
class HookEventType(Enum):
    """Hook事件类型"""
    AGENT_STARTING = "agent_starting"        # Agent启动前
    AGENT_STARTED = "agent_started"          # Agent启动后
    TOOL_PRE_CALL = "tool_pre_call"          # 工具调用前
    TOOL_POST_CALL = "tool_post_call"        # 工具调用后
    TOOL_CALL_ERROR = "tool_call_error"      # 工具调用错误
    MESSAGE_RECEIVED = "message_received"    # 收到消息
    MESSAGE_SENT = "message_sent"            # 发送消息后
    DATA_READ_PRE = "data_read_pre"          # 数据读取前
    DATA_READ_POST = "data_read_post"        # 数据读取后
    DATA_WRITE_PRE = "data_write_pre"        # 数据写入前
    DATA_WRITE_POST = "data_write_post"      # 数据写入后
```

### Hook执行优先级
```python
class HookPriority(Enum):
    """Hook执行优先级"""
    HIGHEST = 1000      # 最高优先级（系统级）
    HIGH = 800         # 高优先级（安全/审计）
    MEDIUM = 500       # 中优先级（业务逻辑）
    LOW = 200          # 低优先级（监控/日志）
    LOWEST = 0         # 最低优先级（清理）
```

## 实施计划

### 阶段1: 核心框架实现（2-3周）
- 实现Hook注册表和分发器
- 定义标准Hook接口和事件类型
- 实现基本的Hook执行器

### 阶段2: 核心Hook插件（2-3周）
- 实现权限校验Hook（OPA集成）
- 实现审计日志Hook
- 实现性能监控Hook
- 实现数据缓存Hook

### 阶段3: 安全机制（1-2周）
- 实现Hook代码签名验证
- 实现Hook沙箱执行环境
- 完善权限控制和审计

### 阶段4: 监控和运维（1-2周）
- 实现Hook性能监控
- 实现Hook使用统计
- 完善配置管理和部署工具

### 阶段5: 优化和文档（1周）
- 性能优化和压力测试
- 编写完整的开发文档
- 生产环境部署和验证

## 成功指标

### 技术指标
1. **Hook执行性能**: 
   - 单个Hook执行延迟 < 10ms
   - Hook链执行延迟 < 50ms
   - 内存使用稳定，无内存泄漏
2. **系统稳定性**:
   - Hook执行成功率 > 99.9%
   - Hook错误隔离率 = 100%
   - 系统可用性 > 99.99%
3. **扩展性指标**:
   - 新Hook开发时间 < 1天
   - Hook配置变更生效时间 < 1秒
   - 支持动态Hook加载/卸载

### 业务指标
1. **开发效率**: 横切关注点开发时间减少60%
2. **代码质量**: 代码重复率降低70%
3. **维护成本**: 系统维护工作量减少40%
4. **系统安全**: 安全漏洞减少80%

## 示例用例

### 权限校验Hook示例
```python
class PermissionHook(BaseHook):
    """权限校验Hook"""
    
    def __init__(self, opa_endpoint: str):
        super().__init__()
        self.opa_client = OPAClient(opa_endpoint)
        
    async def execute(self, context: HookContext, **kwargs) -> HookResult:
        """执行权限校验"""
        if context.event_type == "tool_pre_call":
            # 构建权限检查输入
            input_data = {
                "user": context.user_id,
                "action": "execute",
                "resource": {
                    "type": "tool",
                    "id": context.tool_name
                }
            }
            
            # 调用OPA进行权限校验
            result = await self.opa_client.check_permission(
                policy_name="graphiti_access_policy",
                input_data=input_data
            )
            
            if not result.get("allow", False):
                return HookResult(
                    success=False,
                    message="Permission denied",
                    should_continue=False  # 停止执行
                )
                
        return HookResult(success=True)
```

### 审计日志Hook示例
```python
class AuditHook(BaseHook):
    """审计日志Hook"""
    
    async def execute(self, context: HookContext, **kwargs) -> HookResult:
        """记录审计日志"""
        audit_record = {
            "timestamp": context.timestamp.isoformat(),
            "event_type": context.event_type,
            "user_id": context.user_id,
            "tool_name": context.tool_name,
            "action": "execute",
            "result": kwargs.get("result", {})
        }
        
        # 存储审计记录
        await self._store_audit_record(audit_record)
        
        return HookResult(success=True)
```

## 相关文档

1. [Hook系统模块设计](../modules/hook_system/DESIGN.md)
2. [权限校验模块设计](../modules/permission_checker/DESIGN.md)
3. [OpenHarness Hook规范](https://openharness.io/docs/hooks/)
4. [安全策略文档](../../security/SECURITY.md)

## 决策记录

- **决策者**: 平台架构委员会
- **参与人员**: 架构师、开发团队、安全专家
- **决策时间**: 2026-04-13
- **评审周期**: 每季度评审一次

## 备注

本决策将作为Graphiti系统可扩展性架构的基础，所有新的横切关注点都应通过Hook系统实现。现有代码将逐步迁移到Hook架构。

**风险提示**: Hook系统的复杂性可能导致调试困难，需要配套完善的监控和调试工具。