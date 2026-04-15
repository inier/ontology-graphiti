# Hook System 模块设计文档

> **优先级**: P1 | **相关 ADR**: ADR-027

## 1. 模块概述

**版本**: 1.0.0 | **日期**: 2026-04-12 | **作者**: 平台架构组

### 1.1 模块定位

Hook系统模块是Graphiti系统的**可扩展性核心**，基于OpenHarness的Hook机制，为Agent生命周期提供细粒度的**拦截、增强、监控**能力。通过Hook系统，可以在不修改核心代码的情况下，实现策略注入、权限校验、审计日志、性能监控等横切关注点。

### 1.2 核心职责

| 维度 | 价值 | 说明 |
|------|------|------|
| **可扩展性** | 插件化架构 | 通过Hook机制实现功能的热插拔，无需修改核心代码 |
| **策略注入** | 运行时决策 | 在关键执行点（如工具调用前）注入业务策略（如OPA校验） |
| **可观测性** | 全链路监控 | 通过Hook收集性能指标、日志、追踪信息 |
| **安全增强** | 防御性编程 | 在关键操作前后添加安全检查，实现深度防御 |
| **AOP实现** | 横切关注点 | 将日志、事务、缓存等横切关注点统一管理 |

### 1.3 架构位置

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                         OpenHarness Agent 基础设施层                         │
│  ┌─────────────────┐  ┌─────────────────┐  ┌─────────────────┐           │
│  │ Commander Agent │  │Intelligence Agent│  │Operations Agent │           │
│  └────────┬────────┘  └────────┬────────┘  └────────┬────────┘           │
│           │                    │                    │                    │
│           └────────────────────┼────────────────────┘                    │
│                                ▼                                            │
│                    ┌─────────────────────┐                                  │
│                    │  Swarm Coordinator  │                                  │
│                    │    (OpenHarness)    │                                  │
│                    └──────────┬──────────┘                                  │
│                               │                                              │
│         ┌─────────────────────┼─────────────────────┐                       │
│         ▼                     ▼                     ▼                       │
│  ┌─────────────┐      ┌─────────────┐       ┌─────────────┐                │
│  │Tool Registry│      │  Hook System │      │Permission   │                │
│  │  (43+工具)  │      │ (Pre/Post)   │      │  Checker    │                │
│  └─────────────┘      └─────────────┘       └─────────────┘                │
│                               │                                              │
│         ┌─────────────────────┼─────────────────────┐                       │
│         ▼                     ▼                     ▼                       │
│  ┌─────────────┐      ┌─────────────┐       ┌─────────────┐                │
│  │  Python     │      │   Graphiti   │      │     OPA     │                │
│  │  Skills     │      │ (双时态图谱层) │      │  (策略治理层)  │                │
│  └─────────────┘      └─────────────┘       └─────────────┘                │
```

---

## 2. 架构设计

### 2.1 系统架构

```
┌─────────────────────────────────────────────────────────────────────────────────────┐
│                              Hook系统模块 (Hook System)                               │
├─────────────────────────────────────────────────────────────────────────────────────┤
│                                                                                       │
│  ┌─────────────────────────────────────────────────────────────────────────────┐    │
│  │                         Hook注册表 (Hook Registry)                             │    │
│  │  • Hook注册/注销                                                              │    │
│  │  • Hook优先级管理                                                             │    │
│  │  • Hook依赖解析                                                               │    │
│  │  • Hook配置持久化                                                             │    │
│  └─────────────────────────────────────────────────────────────────────────────┘    │
│                                      │                                                │
│         ┌────────────────────────────┼────────────────────────────┐                  │
│         ▼                            ▼                            ▼                  │
│  ┌──────────────┐          ┌──────────────┐          ┌──────────────┐              │
│  │   Hook分发器  │          │   Hook执行器  │          │   Hook编排器  │              │
│  │ (Hook        │          │  (Hook       │          │  (Hook       │              │
│  │  Dispatcher) │          │   Executor)  │          │   Orchestrator)│              │
│  │  • 事件分发  │          │  • 异步执行  │          │  • 执行顺序   │              │
│  │  • 事件过滤  │          │  • 超时控制  │          │  • 依赖管理   │              │
│  │  • 负载均衡  │          │  • 错误处理  │          │  • 并发控制   │              │
│  └──────────────┘          └──────────────┘          └──────────────┘              │
│                                      │                                                │
│         ┌────────────────────────────┼────────────────────────────┐                  │
│         ▼                            ▼                            ▼                  │
│  ┌──────────────┐          ┌──────────────┐          ┌──────────────┐              │
│  │   Hook监控器  │          │   Hook缓存    │          │   Hook存储    │              │
│  │ (Hook        │          │  (Hook       │          │  (Hook       │              │
│  │  Monitor)    │          │   Cache)     │          │   Storage)   │              │
│  │  • 性能监控  │          │  • 结果缓存  │          │  • 配置存储  │              │
│  │  • 健康检查  │          │  • 状态缓存  │          │  • 历史记录   │              │
│  │  • 告警规则  │          │  • 缓存淘汰  │          │  • 审计日志   │              │
│  └──────────────┘          └──────────────┘          └──────────────┘              │
│                                      │                                                │
│                                      ▼                                                │
│  ┌─────────────────────────────────────────────────────────────────────────────┐    │
│  │                         Hook插件接口 (Hook Plugins)                           │    │
│  │  ┌────────────┐ ┌────────────┐ ┌────────────┐ ┌────────────┐ ┌────────────┐│    │
│  │  │  权限Hook  │ │  日志Hook  │ │ 监控Hook   │ │ 缓存Hook   │ │ 策略Hook   ││    │
│  │  │ (OPA集成)  │ │ (结构化日志) │ │(性能指标)  │ │(结果缓存)  │ │(业务规则)  ││    │
│  │  └────────────┘ └────────────┘ └────────────┘ └────────────┘ └────────────┘│    │
│  └─────────────────────────────────────────────────────────────────────────────┘    │
│                                                                                       │
└─────────────────────────────────────────────────────────────────────────────────────┘
```

### 2.2 核心组件

#### 2.2.1 Hook注册表 (HookRegistry)
- **职责**: 管理所有Hook的注册信息，提供Hook发现和配置管理
- **功能**:
  - Hook的动态注册和注销
  - Hook优先级和依赖关系管理
  - Hook配置的持久化和版本管理
  - Hook的启用/禁用状态管理

#### 2.2.2 Hook分发器 (HookDispatcher)
- **职责**: 根据事件类型分发Hook执行请求
- **功能**:
  - 事件监听和触发
  - Hook的查找和过滤
  - 执行顺序的确定
  - 负载均衡和故障转移

#### 2.2.3 Hook执行器 (HookExecutor)
- **职责**: 执行具体的Hook逻辑
- **功能**:
  - 同步/异步执行模式
  - 超时控制和错误处理
  - 资源管理和清理
  - 结果收集和聚合

#### 2.2.4 Hook编排器 (HookOrchestrator)
- **职责**: 管理Hook之间的依赖和顺序
- **功能**:
  - Hook依赖解析
  - 并行/串行执行控制
  - 事务管理和回滚
  - 执行流程可视化

### 2.3 Hook生命周期

```
┌─────────────────┐    ┌─────────────────┐    ┌─────────────────┐
│   Hook注册阶段   │    │   Hook执行阶段   │    │   Hook清理阶段   │
│                 │    │                 │    │                 │
│ 1. Hook定义     │───▶│ 4. 事件触发     │───▶│ 7. 结果收集     │
│    • 实现接口   │    │    • Agent启动  │    │    • 聚合结果    │
│    • 定义元数据 │    │    • 工具调用   │    │    • 错误处理    │
│                 │    │    • 消息发送   │    │                 │
│ 2. Hook注册     │    │ 5. Hook查找     │    │ 8. 资源清理     │
│    • 注册到系统 │    │    • 按事件类型  │    │    • 连接关闭    │
│    • 设置优先级 │    │    • 按优先级   │    │    • 缓存清除    │
│                 │    │                 │    │                 │
│ 3. Hook配置     │    │ 6. Hook执行     │    │ 9. 状态更新     │
│    • 参数设置   │───▶│    • 同步/异步  │───▶│    • 监控指标    │
│    • 启用/禁用  │    │    • 超时控制   │    │    • 审计日志    │
│                 │    │    • 错误处理   │    │                 │
└─────────────────┘    └─────────────────┘    └─────────────────┘
```

### 2.4 Hook事件类型

#### 2.4.1 Agent生命周期事件
```python
class AgentLifecycleEvent(Enum):
    """Agent生命周期事件"""
    AGENT_STARTING = "agent_starting"        # Agent启动前
    AGENT_STARTED = "agent_started"          # Agent启动后
    AGENT_STOPPING = "agent_stopping"        # Agent停止前
    AGENT_STOPPED = "agent_stopped"          # Agent停止后
    AGENT_ERROR = "agent_error"              # Agent发生错误
```

#### 2.4.2 工具调用事件
```python
class ToolLifecycleEvent(Enum):
    """工具生命周期事件"""
    TOOL_PRE_CALL = "tool_pre_call"          # 工具调用前
    TOOL_POST_CALL = "tool_post_call"        # 工具调用后
    TOOL_CALL_ERROR = "tool_call_error"      # 工具调用错误
    TOOL_CALL_TIMEOUT = "tool_call_timeout"  # 工具调用超时
```

#### 2.4.3 消息处理事件
```python
class MessageLifecycleEvent(Enum):
    """消息处理事件"""
    MESSAGE_RECEIVED = "message_received"    # 收到消息
    MESSAGE_PROCESSING = "message_processing" # 消息处理中
    MESSAGE_PROCESSED = "message_processed"   # 消息处理后
    MESSAGE_SENDING = "message_sending"       # 发送消息前
    MESSAGE_SENT = "message_sent"             # 发送消息后
```

#### 2.4.4 数据访问事件
```python
class DataAccessEvent(Enum):
    """数据访问事件"""
    DATA_READ_PRE = "data_read_pre"          # 数据读取前
    DATA_READ_POST = "data_read_post"        # 数据读取后
    DATA_WRITE_PRE = "data_write_pre"        # 数据写入前
    DATA_WRITE_POST = "data_write_post"      # 数据写入后
    DATA_UPDATE_PRE = "data_update_pre"      # 数据更新前
    DATA_UPDATE_POST = "data_update_post"    # 数据更新后
```

#### 2.4.5 策略检查事件
```python
class PolicyCheckEvent(Enum):
    """策略检查事件"""
    POLICY_CHECK_PRE = "policy_check_pre"    # 策略检查前
    POLICY_CHECK_POST = "policy_check_post"  # 策略检查后
    POLICY_ENFORCEMENT = "policy_enforcement" # 策略强制执行
```

---

## 3. 核心实现

### 3.1 核心接口设计

#### 3.1.1 Hook基础接口
```python
# core/hook/hook_base.py
from typing import Dict, Any, Optional, Awaitable, Callable
from abc import ABC, abstractmethod
from enum import Enum
from dataclasses import dataclass
from datetime import datetime

class HookPriority(Enum):
    """Hook执行优先级"""
    HIGHEST = 1000      # 最高优先级（系统级）
    HIGH = 800         # 高优先级（安全/审计）
    MEDIUM = 500       # 中优先级（业务逻辑）
    LOW = 200          # 低优先级（监控/日志）
    LOWEST = 0         # 最低优先级（清理）

class HookExecutionMode(Enum):
    """Hook执行模式"""
    SYNC = "sync"      # 同步执行
    ASYNC = "async"    # 异步执行
    PARALLEL = "parallel"  # 并行执行

@dataclass
class HookContext:
    """Hook执行上下文"""
    event_type: str               # 事件类型
    timestamp: datetime           # 事件时间戳
    agent_id: Optional[str] = None      # Agent ID
    tool_name: Optional[str] = None     # 工具名称
    message_id: Optional[str] = None    # 消息ID
    user_id: Optional[str] = None       # 用户ID
    session_id: Optional[str] = None    # 会话ID
    request_id: Optional[str] = None    # 请求ID
    metadata: Dict[str, Any] = None     # 元数据

@dataclass
class HookResult:
    """Hook执行结果"""
    success: bool                 # 是否成功
    message: Optional[str] = None # 结果消息
    data: Optional[Dict[str, Any]] = None  # 返回数据
    should_continue: bool = True  # 是否继续执行后续Hook
    error: Optional[Exception] = None  # 错误信息

class BaseHook(ABC):
    """Hook基类"""
    
    def __init__(self):
        self.name = self.__class__.__name__
        self.enabled = True
        self.priority = HookPriority.MEDIUM
        self.execution_mode = HookExecutionMode.SYNC
        self.timeout = 10  # 默认超时时间（秒）
        
    @abstractmethod
    async def execute(self, 
                     context: HookContext,
                     **kwargs) -> HookResult:
        """执行Hook逻辑"""
        pass
        
    def get_dependencies(self) -> list[str]:
        """获取Hook依赖"""
        return []
        
    def get_metadata(self) -> Dict[str, Any]:
        """获取Hook元数据"""
        return {
            "name": self.name,
            "enabled": self.enabled,
            "priority": self.priority.value,
            "execution_mode": self.execution_mode.value,
            "timeout": self.timeout,
            "dependencies": self.get_dependencies()
        }
```

#### 3.1.2 Hook注册表接口
```python
# core/hook/registry.py
from typing import Dict, List, Optional, Type, Set
from collections import defaultdict
import asyncio
from datetime import datetime

class HookRegistry:
    """Hook注册表"""
    
    def __init__(self):
        self.hooks: Dict[str, List[BaseHook]] = defaultdict(list)
        self.hook_instances: Dict[str, BaseHook] = {}
        self.event_types: Set[str] = set()
        
    def register_hook(self, 
                     hook_instance: BaseHook,
                     event_types: List[str]) -> bool:
        """注册Hook"""
        if not hook_instance.enabled:
            return False
            
        hook_name = hook_instance.name
        if hook_name in self.hook_instances:
            print(f"Warning: Hook {hook_name} already registered, skipping")
            return False
            
        # 存储Hook实例
        self.hook_instances[hook_name] = hook_instance
        
        # 为每个事件类型注册Hook
        for event_type in event_types:
            self.hooks[event_type].append(hook_instance)
            self.event_types.add(event_type)
            
        # 按优先级排序
        for event_type in self.hooks:
            self.hooks[event_type].sort(
                key=lambda h: h.priority.value, 
                reverse=True
            )
            
        print(f"Hook registered: {hook_name} for events: {event_types}")
        return True
        
    def unregister_hook(self, hook_name: str) -> bool:
        """注销Hook"""
        if hook_name not in self.hook_instances:
            return False
            
        hook_instance = self.hook_instances[hook_name]
        
        # 从所有事件类型中移除Hook
        for event_type in list(self.hooks.keys()):
            if hook_instance in self.hooks[event_type]:
                self.hooks[event_type].remove(hook_instance)
                
        # 清理空的事件类型
        empty_events = [
            event for event, hooks in self.hooks.items() 
            if not hooks
        ]
        for event in empty_events:
            del self.hooks[event]
            self.event_types.remove(event)
            
        # 移除Hook实例
        del self.hook_instances[hook_name]
        
        print(f"Hook unregistered: {hook_name}")
        return True
        
    def get_hooks_for_event(self, event_type: str) -> List[BaseHook]:
        """获取指定事件类型的Hook"""
        return self.hooks.get(event_type, [])
        
    def get_all_hooks(self) -> Dict[str, List[BaseHook]]:
        """获取所有Hook"""
        return dict(self.hooks)
        
    def get_hook_instance(self, hook_name: str) -> Optional[BaseHook]:
        """获取Hook实例"""
        return self.hook_instances.get(hook_name)
        
    def is_event_supported(self, event_type: str) -> bool:
        """检查事件类型是否支持"""
        return event_type in self.event_types
```

#### 3.1.3 Hook分发器接口
```python
# core/hook/dispatcher.py
from typing import Dict, Any, List, Optional
import asyncio
from datetime import datetime

class HookDispatcher:
    """Hook分发器"""
    
    def __init__(self, registry: HookRegistry):
        self.registry = registry
        self.execution_stats: Dict[str, Dict[str, Any]] = {}
        
    async def dispatch_event(self,
                            event_type: str,
                            context_data: Dict[str, Any],
                            **kwargs) -> Dict[str, Any]:
        """分发事件"""
        if not self.registry.is_event_supported(event_type):
            return {"success": True, "skipped": True, "message": f"Event type {event_type} not supported"}
            
        # 创建执行上下文
        context = HookContext(
            event_type=event_type,
            timestamp=datetime.utcnow(),
            **context_data
        )
        
        # 获取相关Hook
        hooks = self.registry.get_hooks_for_event(event_type)
        if not hooks:
            return {"success": True, "skipped": True, "message": "No hooks registered for this event"}
            
        # 执行Hook
        results = await self._execute_hooks(hooks, context, **kwargs)
        
        # 更新执行统计
        self._update_execution_stats(event_type, results)
        
        return {
            "success": all(r["result"].success for r in results),
            "results": results,
            "total_hooks": len(hooks),
            "executed_hooks": len(results)
        }
        
    async def _execute_hooks(self,
                            hooks: List[BaseHook],
                            context: HookContext,
                            **kwargs) -> List[Dict[str, Any]]:
        """执行Hook列表"""
        results = []
        
        for hook in hooks:
            if not hook.enabled:
                continue
                
            try:
                # 根据执行模式选择执行方式
                if hook.execution_mode == HookExecutionMode.SYNC:
                    result = await self._execute_sync(hook, context, **kwargs)
                elif hook.execution_mode == HookExecutionMode.ASYNC:
                    result = await self._execute_async(hook, context, **kwargs)
                elif hook.execution_mode == HookExecutionMode.PARALLEL:
                    result = await self._execute_parallel(hook, context, **kwargs)
                else:
                    result = HookResult(
                        success=False,
                        message=f"Unknown execution mode: {hook.execution_mode}"
                    )
                    
                results.append({
                    "hook_name": hook.name,
                    "priority": hook.priority.value,
                    "execution_mode": hook.execution_mode.value,
                    "result": result
                })
                
                # 如果Hook要求停止执行，则中断
                if not result.should_continue:
                    results.append({
                        "hook_name": "system",
                        "priority": 1000,
                        "execution_mode": HookExecutionMode.SYNC.value,
                        "result": HookResult(
                            success=False,
                            message="Execution stopped by hook",
                            should_continue=False
                        )
                    })
                    break
                    
            except asyncio.TimeoutError:
                results.append({
                    "hook_name": hook.name,
                    "priority": hook.priority.value,
                    "execution_mode": hook.execution_mode.value,
                    "result": HookResult(
                        success=False,
                        message=f"Hook execution timeout after {hook.timeout}s",
                        should_continue=True
                    )
                })
            except Exception as e:
                results.append({
                    "hook_name": hook.name,
                    "priority": hook.priority.value,
                    "execution_mode": hook.execution_mode.value,
                    "result": HookResult(
                        success=False,
                        message=f"Hook execution error: {str(e)}",
                        error=e,
                        should_continue=True
                    )
                })
                
        return results
        
    async def _execute_sync(self,
                           hook: BaseHook,
                           context: HookContext,
                           **kwargs) -> HookResult:
        """同步执行Hook"""
        return await asyncio.wait_for(
            hook.execute(context, **kwargs),
            timeout=hook.timeout
        )
        
    async def _execute_async(self,
                            hook: BaseHook,
                            context: HookContext,
                            **kwargs) -> HookResult:
        """异步执行Hook"""
        # 创建异步任务
        task = asyncio.create_task(
            hook.execute(context, **kwargs)
        )
        
        try:
            return await asyncio.wait_for(task, timeout=hook.timeout)
        except asyncio.CancelledError:
            task.cancel()
            raise
            
    async def _execute_parallel(self,
                               hook: BaseHook,
                               context: HookContext,
                               **kwargs) -> HookResult:
        """并行执行Hook（通常用于I/O密集型操作）"""
        # 在实际场景中，这可能涉及多个协程或线程
        # 这里简化为异步执行
        return await self._execute_async(hook, context, **kwargs)
        
    def _update_execution_stats(self,
                               event_type: str,
                               results: List[Dict[str, Any]]):
        """更新执行统计"""
        if event_type not in self.execution_stats:
            self.execution_stats[event_type] = {
                "total_executions": 0,
                "successful_executions": 0,
                "failed_executions": 0,
                "average_latency": 0,
                "last_execution": datetime.utcnow()
            }
            
        stats = self.execution_stats[event_type]
        stats["total_executions"] += len(results)
        stats["successful_executions"] += sum(
            1 for r in results if r["result"].success
        )
        stats["failed_executions"] += sum(
            1 for r in results if not r["result"].success
        )
        stats["last_execution"] = datetime.utcnow()
```

### 3.2 具体Hook实现

#### 3.2.1 权限校验Hook
```python
# core/hook/impl/permission_hook.py
from typing import Dict, Any
from ..hook_base import BaseHook, HookContext, HookResult, HookPriority
from core.permission.opa_client import OPAClient

class PermissionHook(BaseHook):
    """权限校验Hook"""
    
    def __init__(self, opa_endpoint: str):
        super().__init__()
        self.name = "PermissionHook"
        self.priority = HookPriority.HIGH  # 高优先级，在业务逻辑前执行
        self.opa_client = OPAClient(opa_endpoint)
        
    async def execute(self, 
                     context: HookContext,
                     **kwargs) -> HookResult:
        """执行权限校验"""
        # 根据事件类型决定是否进行权限校验
        if context.event_type in ["tool_pre_call", "data_write_pre", "data_update_pre"]:
            try:
                # 构建权限检查输入
                input_data = {
                    "user": context.user_id,
                    "action": self._map_event_to_action(context.event_type),
                    "resource": {
                        "type": self._get_resource_type(context),
                        "id": self._get_resource_id(context)
                    },
                    "context": context.metadata or {}
                }
                
                # 调用OPA进行权限校验
                result = await self.opa_client.check_permission(
                    policy_name="graphiti_access_policy",
                    input_data=input_data
                )
                
                if not result.get("allow", False):
                    return HookResult(
                        success=False,
                        message=f"Permission denied: {result.get('reason', 'No reason provided')}",
                        should_continue=False  # 权限校验失败，停止执行
                    )
                    
                return HookResult(
                    success=True,
                    message="Permission check passed",
                    data={"opa_result": result}
                )
                
            except Exception as e:
                return HookResult(
                    success=False,
                    message=f"Permission check error: {str(e)}",
                    error=e,
                    should_continue=False  # 权限检查出错，默认拒绝
                )
                
        # 其他事件类型直接通过
        return HookResult(
            success=True,
            message="No permission check required for this event type"
        )
        
    def _map_event_to_action(self, event_type: str) -> str:
        """将事件类型映射到操作类型"""
        mapping = {
            "tool_pre_call": "execute",
            "data_read_pre": "read",
            "data_write_pre": "write",
            "data_update_pre": "update",
            "data_delete_pre": "delete"
        }
        return mapping.get(event_type, "unknown")
        
    def _get_resource_type(self, context: HookContext) -> str:
        """获取资源类型"""
        if context.tool_name:
            return "tool"
        elif context.metadata and context.metadata.get("resource_type"):
            return context.metadata["resource_type"]
        return "unknown"
        
    def _get_resource_id(self, context: HookContext) -> str:
        """获取资源ID"""
        if context.tool_name:
            return context.tool_name
        elif context.metadata and context.metadata.get("resource_id"):
            return context.metadata["resource_id"]
        return "unknown"
```

#### 3.2.2 审计日志Hook
```python
# core/hook/impl/audit_hook.py
from typing import Dict, Any
from datetime import datetime
from ..hook_base import BaseHook, HookContext, HookResult, HookPriority
import json

class AuditHook(BaseHook):
    """审计日志Hook"""
    
    def __init__(self, storage_backend: str = "elasticsearch"):
        super().__init__()
        self.name = "AuditHook"
        self.priority = HookPriority.LOW  # 低优先级，在业务逻辑后执行
        self.storage_backend = storage_backend
        
    async def execute(self, 
                     context: HookContext,
                     **kwargs) -> HookResult:
        """记录审计日志"""
        try:
            audit_record = {
                "timestamp": context.timestamp.isoformat(),
                "event_type": context.event_type,
                "user_id": context.user_id,
                "agent_id": context.agent_id,
                "session_id": context.session_id,
                "request_id": context.request_id,
                "resource": {
                    "type": self._get_resource_type(context),
                    "id": self._get_resource_id(context)
                },
                "action": self._map_event_to_action(context.event_type),
                "result": kwargs.get("result", {}),
                "metadata": context.metadata or {},
                "ip_address": self._get_ip_address(context),
                "user_agent": self._get_user_agent(context)
            }
            
            # 存储审计记录
            await self._store_audit_record(audit_record)
            
            return HookResult(
                success=True,
                message="Audit record created",
                data={"audit_id": self._generate_audit_id()}
            )
            
        except Exception as e:
            # 审计失败不应影响业务逻辑
            return HookResult(
                success=False,
                message=f"Audit record creation failed: {str(e)}",
                error=e,
                should_continue=True  # 审计失败不影响主流程
            )
            
    async def _store_audit_record(self, record: Dict[str, Any]):
        """存储审计记录"""
        if self.storage_backend == "elasticsearch":
            await self._store_to_elasticsearch(record)
        elif self.storage_backend == "database":
            await self._store_to_database(record)
        else:
            # 默认存储到文件
            await self._store_to_file(record)
            
    async def _store_to_elasticsearch(self, record: Dict[str, Any]):
        """存储到Elasticsearch"""
        # 实现Elasticsearch存储逻辑
        pass
        
    async def _store_to_database(self, record: Dict[str, Any]):
        """存储到数据库"""
        # 实现数据库存储逻辑
        pass
        
    async def _store_to_file(self, record: Dict[str, Any]):
        """存储到文件"""
        import os
        from pathlib import Path
        
        audit_dir = Path("/var/log/graphiti/audit")
        audit_dir.mkdir(parents=True, exist_ok=True)
        
        # 按日期分割文件
        date_str = datetime.utcnow().strftime("%Y-%m-%d")
        file_path = audit_dir / f"audit_{date_str}.log"
        
        with open(file_path, "a") as f:
            f.write(json.dumps(record) + "\n")
            
    def _generate_audit_id(self) -> str:
        """生成审计ID"""
        import uuid
        return str(uuid.uuid4())
        
    def _get_ip_address(self, context: HookContext) -> Optional[str]:
        """获取IP地址"""
        return context.metadata.get("ip_address") if context.metadata else None
        
    def _get_user_agent(self, context: HookContext) -> Optional[str]:
        """获取User-Agent"""
        return context.metadata.get("user_agent") if context.metadata else None
```

#### 3.2.3 性能监控Hook
```python
# core/hook/impl/metrics_hook.py
from typing import Dict, Any
from datetime import datetime
from ..hook_base import BaseHook, HookContext, HookResult, HookPriority
import time

class MetricsHook(BaseHook):
    """性能监控Hook"""
    
    def __init__(self, metrics_collector: Any):
        super().__init__()
        self.name = "MetricsHook"
        self.priority = HookPriority.LOWEST  # 最低优先级，最后执行
        self.metrics_collector = metrics_collector
        self.execution_times: Dict[str, float] = {}
        
    async def execute(self, 
                     context: HookContext,
                     **kwargs) -> HookResult:
        """收集性能指标"""
        start_time = time.time()
        
        try:
            # 记录事件开始
            await self._record_event_start(context)
            
            # 等待业务逻辑执行（如果有的话）
            result = kwargs.get("result", {})
            
            # 计算执行时间
            execution_time = time.time() - start_time
            
            # 记录性能指标
            await self._record_metrics(context, execution_time, result)
            
            return HookResult(
                success=True,
                message="Metrics collected",
                data={
                    "execution_time_ms": execution_time * 1000,
                    "event_type": context.event_type
                }
            )
            
        except Exception as e:
            # 监控失败不应影响业务逻辑
            return HookResult(
                success=False,
                message=f"Metrics collection failed: {str(e)}",
                error=e,
                should_continue=True
            )
            
    async def _record_event_start(self, context: HookContext):
        """记录事件开始"""
        metric_name = f"graphiti_events_total"
        labels = {
            "event_type": context.event_type,
            "agent_id": context.agent_id or "unknown",
            "status": "started"
        }
        
        self.metrics_collector.increment_counter(metric_name, labels)
        
    async def _record_metrics(self, 
                             context: HookContext,
                             execution_time: float,
                             result: Dict[str, Any]):
        """记录性能指标"""
        # 记录执行时间
        metric_name = f"graphiti_execution_duration_seconds"
        labels = {
            "event_type": context.event_type,
            "agent_id": context.agent_id or "unknown",
            "success": str(result.get("success", True))
        }
        
        self.metrics_collector.record_histogram(
            metric_name,
            execution_time,
            labels
        )
        
        # 记录事件完成
        metric_name = f"graphiti_events_total"
        labels["status"] = "completed"
        labels["success"] = str(result.get("success", True))
        
        self.metrics_collector.increment_counter(metric_name, labels)
        
        # 记录错误（如果有）
        if not result.get("success", True):
            error_metric_name = f"graphiti_errors_total"
            error_labels = {
                "event_type": context.event_type,
                "agent_id": context.agent_id or "unknown",
                "error_type": result.get("error_type", "unknown")
            }
            self.metrics_collector.increment_counter(error_metric_name, error_labels)
```

#### 3.2.4 缓存Hook
```python
# core/hook/impl/cache_hook.py
from typing import Dict, Any, Optional
from ..hook_base import BaseHook, HookContext, HookResult, HookPriority
import hashlib
import json

class CacheHook(BaseHook):
    """缓存Hook"""
    
    def __init__(self, cache_backend: str = "redis"):
        super().__init__()
        self.name = "CacheHook"
        self.priority = HookPriority.MEDIUM
        self.cache_backend = cache_backend
        self.cache_client = None
        self.cache_ttl = 300  # 默认5分钟
        
    async def execute(self, 
                     context: HookContext,
                     **kwargs) -> HookResult:
        """处理缓存逻辑"""
        # 根据事件类型决定缓存操作
        if context.event_type == "data_read_pre":
            # 数据读取前：尝试从缓存获取
            return await self._handle_cache_read(context, **kwargs)
        elif context.event_type == "data_read_post":
            # 数据读取后：将结果存入缓存
            return await self._handle_cache_write(context, **kwargs)
        elif context.event_type in ["data_write_post", "data_update_post", "data_delete_post"]:
            # 数据变更后：使缓存失效
            return await self._handle_cache_invalidate(context, **kwargs)
        else:
            return HookResult(
                success=True,
                message="No cache operation needed for this event type"
            )
            
    async def _handle_cache_read(self,
                                context: HookContext,
                                **kwargs) -> HookResult:
        """处理缓存读取"""
        cache_key = self._generate_cache_key(context)
        
        try:
            cached_data = await self._get_from_cache(cache_key)
            if cached_data is not None:
                return HookResult(
                    success=True,
                    message="Cache hit",
                    data={"cached": True, "data": cached_data},
                    should_continue=False  # 命中缓存，停止后续处理
                )
                
            return HookResult(
                success=True,
                message="Cache miss",
                data={"cached": False}
            )
            
        except Exception as e:
            # 缓存读取失败不应影响主流程
            return HookResult(
                success=False,
                message=f"Cache read error: {str(e)}",
                error=e,
                should_continue=True
            )
            
    async def _handle_cache_write(self,
                                 context: HookContext,
                                 **kwargs) -> HookResult:
        """处理缓存写入"""
        cache_key = self._generate_cache_key(context)
        data_to_cache = kwargs.get("result", {}).get("data")
        
        if data_to_cache is None:
            return HookResult(
                success=True,
                message="No data to cache"
            )
            
        try:
            await self._set_to_cache(cache_key, data_to_cache, ttl=self.cache_ttl)
            return HookResult(
                success=True,
                message="Data cached successfully"
            )
        except Exception as e:
            return HookResult(
                success=False,
                message=f"Cache write error: {str(e)}",
                error=e,
                should_continue=True
            )
            
    async def _handle_cache_invalidate(self,
                                      context: HookContext,
                                      **kwargs) -> HookResult:
        """处理缓存失效"""
        cache_key = self._generate_cache_key(context)
        
        try:
            await self._delete_from_cache(cache_key)
            return HookResult(
                success=True,
                message="Cache invalidated successfully"
            )
        except Exception as e:
            return HookResult(
                success=False,
                message=f"Cache invalidation error: {str(e)}",
                error=e,
                should_continue=True
            )
            
    def _generate_cache_key(self, context: HookContext) -> str:
        """生成缓存键"""
        key_data = {
            "event_type": context.event_type,
            "resource_type": self._get_resource_type(context),
            "resource_id": self._get_resource_id(context),
            "user_id": context.user_id,
            "query_params": context.metadata.get("query_params", {}) if context.metadata else {}
        }
        
        # 使用JSON序列化和哈希生成唯一键
        key_str = json.dumps(key_data, sort_keys=True)
        key_hash = hashlib.md5(key_str.encode()).hexdigest()
        
        return f"graphiti:cache:{key_hash}"
        
    async def _get_from_cache(self, key: str) -> Optional[Any]:
        """从缓存获取数据"""
        if self.cache_backend == "redis":
            return await self._get_from_redis(key)
        else:
            return None
            
    async def _set_to_cache(self, key: str, value: Any, ttl: int):
        """设置缓存数据"""
        if self.cache_backend == "redis":
            await self._set_to_redis(key, value, ttl)
            
    async def _delete_from_cache(self, key: str):
        """删除缓存数据"""
        if self.cache_backend == "redis":
            await self._delete_from_redis(key)
            
    async def _get_from_redis(self, key: str) -> Optional[Any]:
        """从Redis获取数据"""
        # 实现Redis读取逻辑
        pass
        
    async def _set_to_redis(self, key: str, value: Any, ttl: int):
        """设置Redis数据"""
        # 实现Redis写入逻辑
        pass
        
    async def _delete_from_redis(self, key: str):
        """删除Redis数据"""
        # 实现Redis删除逻辑
        pass
```

### 3.3 Hook配置管理

#### 3.3.1 配置文件格式
```yaml
# config/hooks.yaml
hooks:
  # 权限校验Hook
  permission_hook:
    enabled: true
    priority: 800  # HIGH
    execution_mode: sync
    timeout: 5
    config:
      opa_endpoint: "http://opa:8181"
      default_policy: "graphiti_access_policy"
      cache_enabled: true
      cache_ttl: 60
      
  # 审计日志Hook
  audit_hook:
    enabled: true
    priority: 200  # LOW
    execution_mode: async
    timeout: 10
    config:
      storage_backend: "elasticsearch"
      elasticsearch_host: "http://elasticsearch:9200"
      index_name: "graphiti-audit-logs"
      retention_days: 90
      
  # 性能监控Hook
  metrics_hook:
    enabled: true
    priority: 0    # LOWEST
    execution_mode: async
    timeout: 3
    config:
      metrics_backend: "prometheus"
      prometheus_port: 9090
      collect_interval: 15
      
  # 缓存Hook
  cache_hook:
    enabled: true
    priority: 500  # MEDIUM
    execution_mode: sync
    timeout: 2
    config:
      cache_backend: "redis"
      redis_host: "redis:6379"
      cache_ttl: 300
      max_cache_size: 10000
      
# 事件类型映射
event_mappings:
  agent_lifecycle:
    - AGENT_STARTING
    - AGENT_STARTED
    - AGENT_STOPPING
    - AGENT_STOPPED
    - AGENT_ERROR
    
  tool_lifecycle:
    - TOOL_PRE_CALL
    - TOOL_POST_CALL
    - TOOL_CALL_ERROR
    - TOOL_CALL_TIMEOUT
    
  message_lifecycle:
    - MESSAGE_RECEIVED
    - MESSAGE_PROCESSING
    - MESSAGE_PROCESSED
    - MESSAGE_SENDING
    - MESSAGE_SENT
    
# Hook注册
registrations:
  - hook: permission_hook
    events:
      - TOOL_PRE_CALL
      - DATA_WRITE_PRE
      - DATA_UPDATE_PRE
      - DATA_DELETE_PRE
      
  - hook: audit_hook
    events:
      - TOOL_PRE_CALL
      - TOOL_POST_CALL
      - DATA_WRITE_POST
      - DATA_UPDATE_POST
      - DATA_DELETE_POST
      
  - hook: metrics_hook
    events:
      - "*"  # 所有事件
      
  - hook: cache_hook
    events:
      - DATA_READ_PRE
      - DATA_READ_POST
      - DATA_WRITE_POST
      - DATA_UPDATE_POST
      - DATA_DELETE_POST
```

---

## 4. 安全设计

### 4.1 Hook安全机制

#### 4.1.1 Hook代码签名
```python
# core/hook/security/hook_validator.py
import hashlib
import json
from typing import Dict, Any, Optional
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.asymmetric import rsa, padding
from cryptography.hazmat.primitives import serialization

class HookSignatureValidator:
    """Hook代码签名验证器"""
    
    def __init__(self, public_key_path: str):
        self.public_key = self._load_public_key(public_key_path)
        
    def validate_hook(self, hook_code: str, signature: str) -> bool:
        """验证Hook代码签名"""
        try:
            # 计算代码哈希
            code_hash = hashlib.sha256(hook_code.encode()).hexdigest()
            
            # 验证签名
            signature_bytes = bytes.fromhex(signature)
            self.public_key.verify(
                signature_bytes,
                code_hash.encode(),
                padding.PSS(
                    mgf=padding.MGF1(hashes.SHA256()),
                    salt_length=padding.PSS.MAX_LENGTH
                ),
                hashes.SHA256()
            )
            return True
        except Exception as e:
            print(f"Signature validation failed: {e}")
            return False
            
    def _load_public_key(self, path: str) -> rsa.RSAPublicKey:
        """加载公钥"""
        with open(path, "rb") as key_file:
            public_key = serialization.load_pem_public_key(
                key_file.read()
            )
        return public_key
```

#### 4.1.2 Hook沙箱执行
```python
# core/hook/security/hook_sandbox.py
import asyncio
from typing import Dict, Any, Callable
from restrictedpython import compile_restricted, safe_builtins
from restrictedpython import limited_builtins

class HookSandbox:
    """Hook沙箱执行环境"""
    
    def __init__(self):
        self.allowed_modules = {
            "datetime", "json", "hashlib", "typing",
            "collections", "itertools", "math", "re"
        }
        self.safe_builtins = safe_builtins.copy()
        
    async def execute_in_sandbox(self,
                                hook_code: str,
                                context: Dict[str, Any]) -> Dict[str, Any]:
        """在沙箱中执行Hook代码"""
        try:
            # 编译受限制的代码
            byte_code = compile_restricted(
                hook_code,
                filename='<hook>',
                mode='exec'
            )
            
            # 创建安全的执行环境
            execution_globals = {
                '__builtins__': self.safe_builtins,
                'context': context,
                'result': {}
            }
            
            # 执行代码
            exec(byte_code, execution_globals)
            
            # 获取执行结果
            result = execution_globals.get('result', {})
            
            return {
                "success": True,
                "result": result
            }
            
        except Exception as e:
            return {
                "success": False,
                "error": str(e),
                "result": {}
            }
```

### 4.2 访问控制

#### 4.2.1 Hook权限模型
```python
# core/hook/security/permission_model.py
from typing import Set, List, Optional
from enum import Enum
from dataclasses import dataclass

class HookPermission(Enum):
    """Hook权限"""
    REGISTER = "hook.register"      # 注册Hook
    UNREGISTER = "hook.unregister"  # 注销Hook
    EXECUTE = "hook.execute"        # 执行Hook
    CONFIGURE = "hook.configure"    # 配置Hook
    MONITOR = "hook.monitor"        # 监控Hook

@dataclass
class HookRole:
    """Hook角色"""
    name: str
    permissions: Set[HookPermission]
    description: str

class HookPermissionManager:
    """Hook权限管理器"""
    
    def __init__(self):
        # 定义预置角色
        self.roles = {
            "hook_admin": HookRole(
                name="hook_admin",
                permissions={
                    HookPermission.REGISTER,
                    HookPermission.UNREGISTER,
                    HookPermission.EXECUTE,
                    HookPermission.CONFIGURE,
                    HookPermission.MONITOR
                },
                description="Hook管理员，拥有所有权限"
            ),
            "hook_operator": HookRole(
                name="hook_operator",
                permissions={
                    HookPermission.EXECUTE,
                    HookPermission.MONITOR
                },
                description="Hook操作员，只能执行和监控Hook"
            ),
            "hook_viewer": HookRole(
                name="hook_viewer",
                permissions={
                    HookPermission.MONITOR
                },
                description="Hook查看者，只能查看Hook状态"
            )
        }
        
    def check_permission(self,
                        user_role: str,
                        permission: HookPermission) -> bool:
        """检查权限"""
        role = self.roles.get(user_role)
        if not role:
            return False
            
        return permission in role.permissions
```

---

## 5. 监控与运维

### 5.1 监控指标

#### 5.1.1 Hook性能指标
```python
# core/hook/monitoring/hook_metrics.py
from typing import Dict, List
from dataclasses import dataclass
from datetime import datetime
from enum import Enum

class HookMetricType(Enum):
    """Hook指标类型"""
    EXECUTION_COUNT = "execution_count"
    EXECUTION_TIME = "execution_time"
    SUCCESS_RATE = "success_rate"
    ERROR_COUNT = "error_count"
    CACHE_HIT_RATE = "cache_hit_rate"

@dataclass
class HookMetric:
    """Hook监控指标"""
    hook_name: str
    metric_type: HookMetricType
    value: float
    labels: Dict[str, str]
    timestamp: datetime

class HookMetricsCollector:
    """Hook指标收集器"""
    
    def __init__(self):
        self.metrics: Dict[str, List[HookMetric]] = {}
        
    def record_execution(self,
                        hook_name: str,
                        event_type: str,
                        execution_time_ms: float,
                        success: bool):
        """记录Hook执行"""
        # 记录执行次数
        self._record_counter(
            hook_name=hook_name,
            metric_type=HookMetricType.EXECUTION_COUNT,
            event_type=event_type,
            value=1
        )
        
        # 记录执行时间
        self._record_histogram(
            hook_name=hook_name,
            metric_type=HookMetricType.EXECUTION_TIME,
            event_type=event_type,
            value=execution_time_ms
        )
        
        # 记录成功/失败
        if success:
            self._record_counter(
                hook_name=hook_name,
                metric_type=HookMetricType.SUCCESS_RATE,
                event_type=event_type,
                value=1
            )
        else:
            self._record_counter(
                hook_name=hook_name,
                metric_type=HookMetricType.ERROR_COUNT,
                event_type=event_type,
                value=1
            )
            
    def _record_counter(self,
                       hook_name: str,
                       metric_type: HookMetricType,
                       event_type: str,
                       value: float):
        """记录计数器指标"""
        metric = HookMetric(
            hook_name=hook_name,
            metric_type=metric_type,
            value=value,
            labels={"event_type": event_type},
            timestamp=datetime.utcnow()
        )
        self._store_metric(metric)
        
    def _record_histogram(self,
                         hook_name: str,
                         metric_type: HookMetricType,
                         event_type: str,
                         value: float):
        """记录直方图指标"""
        metric = HookMetric(
            hook_name=hook_name,
            metric_type=metric_type,
            value=value,
            labels={"event_type": event_type},
            timestamp=datetime.utcnow()
        )
        self._store_metric(metric)
        
    def _store_metric(self, metric: HookMetric):
        """存储指标"""
        key = f"{metric.hook_name}:{metric.metric_type.value}"
        if key not in self.metrics:
            self.metrics[key] = []
        self.metrics[key].append(metric)
        
        # 限制历史记录数量
        if len(self.metrics[key]) > 1000:
            self.metrics[key] = self.metrics[key][-500:]
```

### 5.2 告警规则

#### 5.2.1 Hook告警配置
```yaml
# config/hook_alerts.yaml
alerts:
  - name: "hook_high_error_rate"
    description: "Hook错误率过高"
    metric: "graphiti_hook_errors_total"
    condition: "rate_5m > 10"  # 5分钟内错误超过10次
    duration: "5m"
    severity: "warning"
    labels:
      component: "hook_system"
      
  - name: "hook_slow_execution"
    description: "Hook执行过慢"
    metric: "graphiti_hook_execution_duration_seconds"
    condition: "value > 5"    # 执行时间超过5秒
    duration: "2m"
    severity: "warning"
    labels:
      component: "hook_system"
      
  - name: "hook_registry_full"
    description: "Hook注册表已满"
    metric: "graphiti_hook_registry_size"
    condition: "value > 1000"  # 注册Hook超过1000个
    severity: "critical"
    labels:
      component: "hook_registry"
      
  - name: "hook_memory_high"
    description: "Hook内存使用过高"
    metric: "graphiti_hook_memory_usage_bytes"
    condition: "value > 1073741824"  # 内存使用超过1GB
    duration: "5m"
    severity: "critical"
    labels:
      component: "hook_system"
```

---

## 6. 部署与配置

### 6.1 Docker部署配置

#### 6.1.1 Docker Compose配置
```yaml
# docker-compose.hook.yaml
version: '3.8'

services:
  # Hook系统服务
  hook-system:
    build:
      context: .
      dockerfile: docker/hook/Dockerfile
    container_name: hook-system
    ports:
      - "8082:8082"    # Hook管理API端口
      - "8083:8083"    # Hook监控端口
    environment:
      - HOOK_LOG_LEVEL=INFO
      - HOOK_REGISTRY_ENABLED=true
      - HOOK_CACHE_ENABLED=true
      - HOOK_MONITORING_ENABLED=true
      - REDIS_HOST=redis
      - ELASTICSEARCH_HOST=elasticsearch
      - OPA_ENDPOINT=http://opa:8181
    volumes:
      - ./config/hooks:/app/config
      - ./logs/hooks:/app/logs
      - ./hooks/custom:/app/hooks/custom  # 自定义Hook目录
    depends_on:
      - redis
      - elasticsearch
      - opa
    networks:
      - domain-network
      
  # Hook监控服务
  hook-monitor:
    image: prometheus:latest
    container_name: hook-monitor
    ports:
      - "9090:9090"
    volumes:
      - ./config/prometheus.yml:/etc/prometheus/prometheus.yml
      - hook-metrics-data:/prometheus
    command:
      - '--config.file=/etc/prometheus/prometheus.yml'
      - '--storage.tsdb.path=/prometheus'
      - '--web.console.libraries=/etc/prometheus/console_libraries'
      - '--web.console.templates=/etc/prometheus/consoles'
      - '--storage.tsdb.retention.time=200h'
      - '--web.enable-lifecycle'
    networks:
      - domain-network

volumes:
  hook-metrics-data:

networks:
  domain-network:
    driver: bridge
```

### 6.2 配置管理

#### 6.2.1 Hook配置文件
```yaml
# config/hook_config.yaml
hook:
  # 系统配置
  system:
    enabled: true
    log_level: "INFO"
    registry_size_limit: 1000
    execution_timeout_default: 10
    enable_sandbox: true
    
  # 存储配置
  storage:
    registry_backend: "redis"
    cache_backend: "redis"
    audit_backend: "elasticsearch"
    
  # 缓存配置
  cache:
    enabled: true
    ttl_default: 300
    max_size: 10000
    eviction_policy: "lru"
    
  # 监控配置
  monitoring:
    enabled: true
    metrics_port: 8083
    collect_interval: 15
    retention_days: 30
    
  # 安全配置
  security:
    enable_signature_validation: true
    public_key_path: "/app/config/hook_public_key.pem"
    sandbox_enabled: true
    max_hook_size_kb: 100
    
  # Hook插件配置
  plugins:
    permission_hook:
      enabled: true
      opa_endpoint: "http://opa:8181"
      
    audit_hook:
      enabled: true
      elasticsearch_host: "http://elasticsearch:9200"
      
    metrics_hook:
      enabled: true
      prometheus_port: 9090
      
    cache_hook:
      enabled: true
      redis_host: "redis:6379"
      
  # 事件映射
  event_mappings:
    - event: "agent.*"
      description: "Agent生命周期事件"
      
    - event: "tool.*"
      description: "工具调用事件"
      
    - event: "message.*"
      description: "消息处理事件"
      
    - event: "data.*"
      description: "数据访问事件"
```

---

## 7. API文档

### 7.1 REST API

#### 7.1.1 Hook管理API
```
GET    /api/v1/hooks           # 获取所有Hook列表
POST   /api/v1/hooks          # 注册新Hook
GET    /api/v1/hooks/{name}   # 获取Hook详情
PUT    /api/v1/hooks/{name}   # 更新Hook配置
DELETE /api/v1/hooks/{name}   # 注销Hook
POST   /api/v1/hooks/{name}/enable   # 启用Hook
POST   /api/v1/hooks/{name}/disable  # 禁用Hook
```

#### 7.1.2 事件管理API
```
GET    /api/v1/events         # 获取所有事件类型
POST   /api/v1/events/{type}  # 手动触发事件
GET    /api/v1/events/{type}/hooks  # 获取事件关联的Hook
```

#### 7.1.3 监控API
```
GET    /api/v1/metrics        # 获取监控指标
GET    /api/v1/stats          # 获取统计信息
GET    /api/v1/health         # 健康检查
```

### 7.2 WebSocket API

#### 7.2.1 实时事件流
```javascript
// 连接到Hook事件流
const ws = new WebSocket('ws://localhost:8082/hooks/ws');

ws.onopen = () => {
  // 订阅所有Hook事件
  ws.send(JSON.stringify({
    type: 'subscribe',
    channel: 'hook_events',
    filter: { event_type: '*' }
  }));
  
  // 订阅特定Hook的执行事件
  ws.send(JSON.stringify({
    type: 'subscribe',
    channel: 'hook_executions',
    filter: { hook_name: 'permission_hook' }
  }));
};

ws.onmessage = (event) => {
  const data = JSON.parse(event.data);
  console.log('收到Hook事件:', data);
  
  // 处理不同类型的事件
  switch(data.event_type) {
    case 'hook_registered':
      console.log('Hook已注册:', data.hook_name);
      break;
    case 'hook_executed':
      console.log('Hook已执行:', data.hook_name, data.result);
      break;
    case 'hook_error':
      console.error('Hook执行错误:', data.hook_name, data.error);
      break;
  }
};
```

---

## 8. 版本历史

| 版本 | 日期 | 变更说明 |
|------|------|----------|
| v1.0.0 | 2026-04-12 | 初始版本，完整设计Hook系统模块 |
| v0.1.0 | 2026-04-11 | 草案版本，基础架构设计 |

---

**相关文档**:
- [OpenHarness领域适配指南](../openharness_bridge/DESIGN.md)
- [权限校验模块设计](../permission_checker/DESIGN.md)
- [MCP协议集成模块设计](../mcp_protocol/DESIGN.md)
- [安全策略文档](../../security/SECURITY.md)