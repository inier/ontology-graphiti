"""
Hook System 模块
为 Agent 生命周期提供细粒度的拦截、增强、监控能力

Phase 2 扩展: Hook System
"""

import asyncio
import logging
from typing import Any, Callable, Dict, List, Optional
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from functools import wraps

logger = logging.getLogger("hook_system")


class HookPhase(str, Enum):
    """Hook 执行阶段"""
    PRE = "pre"
    POST = "post"
    ON_ERROR = "on_error"


class HookPriority(int, Enum):
    """Hook 优先级（数值越小优先级越高）"""
    CRITICAL = 1
    HIGH = 25
    MEDIUM = 50
    LOW = 75
    DEFAULT = 100


@dataclass
class HookRegistration:
    """Hook 注册信息"""
    name: str
    handler: Callable
    phase: HookPhase
    priority: int = HookPriority.DEFAULT.value
    enabled: bool = True
    description: str = ""
    tags: List[str] = field(default_factory=list)


class HookContext:
    """Hook 执行上下文"""

    def __init__(self, event_name: str, agent_id: str = None, mission_id: str = None):
        self.event_name = event_name
        self.agent_id = agent_id
        self.mission_id = mission_id
        self.data: Dict[str, Any] = {}
        self.timestamp = datetime.now()
        self.errors: List[str] = []

    def set_data(self, key: str, value: Any):
        self.data[key] = value

    def get_data(self, key: str, default: Any = None) -> Any:
        return self.data.get(key, default)

    def add_error(self, error: str):
        self.errors.append(error)


class HookRegistry:
    """Hook 注册表"""

    _instance: Optional['HookRegistry'] = None

    def __init__(self):
        self._hooks: Dict[str, List[HookRegistration]] = {}
        self._global_enabled = True

    @classmethod
    def get_instance(cls) -> 'HookRegistry':
        if cls._instance is None:
            cls._instance = HookRegistry()
        return cls._instance

    def register(
        self,
        event: str,
        name: str,
        handler: Callable,
        phase: HookPhase = HookPhase.POST,
        priority: int = HookPriority.DEFAULT.value,
        description: str = "",
        tags: List[str] = None,
    ) -> bool:
        """注册 Hook"""
        if event not in self._hooks:
            self._hooks[event] = []

        registration = HookRegistration(
            name=name,
            handler=handler,
            phase=phase,
            priority=priority,
            description=description,
            tags=tags or [],
        )

        self._hooks[event].append(registration)
        self._hooks[event].sort(key=lambda h: h.priority)

        logger.info(f"Hook 注册: {event}/{phase.value}/{name} (优先级: {priority})")
        return True

    def unregister(self, event: str, name: str) -> bool:
        """注销 Hook"""
        if event not in self._hooks:
            return False

        original_count = len(self._hooks[event])
        self._hooks[event] = [h for h in self._hooks[event] if h.name != name]

        return len(self._hooks[event]) < original_count

    def get_hooks(self, event: str, phase: HookPhase = None) -> List[HookRegistration]:
        """获取指定事件的 Hook"""
        if event not in self._hooks:
            return []

        hooks = self._hooks[event]
        if phase:
            hooks = [h for h in hooks if h.phase == phase]

        return [h for h in hooks if h.enabled]

    def enable(self, event: str, name: str) -> bool:
        """启用 Hook"""
        if event not in self._hooks:
            return False
        for hook in self._hooks[event]:
            if hook.name == name:
                hook.enabled = True
                return True
        return False

    def disable(self, event: str, name: str) -> bool:
        """禁用 Hook"""
        if event not in self._hooks:
            return False
        for hook in self._hooks[event]:
            if hook.name == name:
                hook.enabled = False
                return True
        return False

    def list_events(self) -> List[str]:
        """列出所有已注册的事件"""
        return list(self._hooks.keys())

    def get_hook_summary(self) -> Dict[str, Any]:
        """获取 Hook 注册汇总"""
        summary = {}
        for event, hooks in self._hooks.items():
            summary[event] = {
                "total": len(hooks),
                "enabled": len([h for h in hooks if h.enabled]),
                "pre": len([h for h in hooks if h.phase == HookPhase.PRE]),
                "post": len([h for h in hooks if h.phase == HookPhase.POST]),
                "on_error": len([h for h in hooks if h.phase == HookPhase.ON_ERROR]),
            }
        return summary


class HookExecutor:
    """Hook 执行器"""

    def __init__(self, registry: HookRegistry = None):
        self.registry = registry or HookRegistry.get_instance()
        self._execution_history: List[Dict[str, Any]] = []

    async def execute_pre_hooks(
        self,
        event: str,
        context: HookContext,
        original_args: tuple = (),
        original_kwargs: dict = None,
    ) -> bool:
        """执行 Pre Hooks（返回 False 表示中断执行）"""
        if not self.registry._global_enabled:
            return True

        hooks = self.registry.get_hooks(event, HookPhase.PRE)
        for hook in hooks:
            try:
                result = hook.handler(context, *original_args, **(original_kwargs or {}))
                if asyncio.iscoroutine(result):
                    result = await result

                if result is False:
                    logger.warning(f"Pre Hook {hook.name} 返回 False，中断执行")
                    return False

            except Exception as e:
                logger.error(f"Pre Hook {hook.name} 执行失败: {e}")
                context.add_error(str(e))
                return False

        return True

    async def execute_post_hooks(
        self,
        event: str,
        context: HookContext,
        result: Any = None,
        error: Exception = None,
    ):
        """执行 Post Hooks"""
        if not self.registry._global_enabled:
            return

        hooks = self.registry.get_hooks(event, HookPhase.POST)
        for hook in hooks:
            try:
                hook_result = hook.handler(context, result)
                if asyncio.iscoroutine(hook_result):
                    await hook_result
            except Exception as e:
                logger.error(f"Post Hook {hook.name} 执行失败: {e}")
                context.add_error(str(e))

    async def execute_error_hooks(self, event: str, context: HookContext, error: Exception):
        """执行 Error Hooks"""
        if not self.registry._global_enabled:
            return

        hooks = self.registry.get_hooks(event, HookPhase.ON_ERROR)
        for hook in hooks:
            try:
                hook_result = hook.handler(context, error)
                if asyncio.iscoroutine(hook_result):
                    await hook_result
            except Exception as e:
                logger.error(f"Error Hook {hook.name} 执行失败: {e}")

    def record_execution(self, event: str, hook_name: str, phase: HookPhase, success: bool):
        """记录 Hook 执行历史"""
        self._execution_history.append({
            "event": event,
            "hook_name": hook_name,
            "phase": phase.value,
            "success": success,
            "timestamp": datetime.now().isoformat(),
        })

        if len(self._execution_history) > 1000:
            self._execution_history = self._execution_history[-1000:]

    def get_execution_history(self, limit: int = 100) -> List[Dict[str, Any]]:
        """获取执行历史"""
        return self._execution_history[-limit:]


class HookDecorator:
    """Hook 装饰器"""

    @staticmethod
    def hook(
        event: str,
        phase: HookPhase = HookPhase.POST,
        priority: int = HookPriority.DEFAULT.value,
        description: str = "",
        tags: List[str] = None,
    ):
        """装饰器：自动注册 Hook"""
        def decorator(func: Callable) -> Callable:
            registry = HookRegistry.get_instance()

            @wraps(func)
            async def async_wrapper(*args, **kwargs):
                context = HookContext(event_name=event)
                executor = HookExecutor(registry)

                if not await executor.execute_pre_hooks(event, context, args, kwargs):
                    return None

                try:
                    result = await func(*args, **kwargs)
                    await executor.execute_post_hooks(event, context, result)
                    return result
                except Exception as e:
                    await executor.execute_error_hooks(event, context, e)
                    raise

            @wraps(func)
            def sync_wrapper(*args, **kwargs):
                context = HookContext(event_name=event)
                executor = HookExecutor(registry)

                if not asyncio.run(executor.execute_pre_hooks(event, context, args, kwargs)):
                    return None

                try:
                    result = func(*args, **kwargs)
                    asyncio.run(executor.execute_post_hooks(event, context, result))
                    return result
                except Exception as e:
                    asyncio.run(executor.execute_error_hooks(event, context, e))
                    raise

            func_name = func.__name__
            registry.register(
                event=event,
                name=func_name,
                handler=async_wrapper if asyncio.iscoroutinefunction(func) else sync_wrapper,
                phase=phase,
                priority=priority,
                description=description,
                tags=tags,
            )

            return async_wrapper if asyncio.iscoroutinefunction(func) else sync_wrapper

        return decorator


def create_logging_hook(phase: HookPhase, event: str) -> Callable:
    """创建日志记录 Hook"""
    async def logging_hook(context: HookContext, *args, **kwargs):
        logger.info(f"[Hook:{event}/{phase.value}] 执行 - {context.event_name}")

    return logging_hook


def create_timing_hook(phase: HookPhase, event: str) -> Callable:
    """创建性能计时 Hook"""
    start_times: Dict[str, float] = {}

    async def timing_hook(context: HookContext, *args, **kwargs):
        if phase == HookPhase.PRE:
            import time
            start_times[context.event_name] = time.perf_counter()
        elif phase == HookPhase.POST:
            import time
            start_time = start_times.pop(context.event_name, None)
            if start_time:
                elapsed_ms = (time.perf_counter() - start_time) * 1000
                logger.info(f"[Hook:{event}/timing] {context.event_name} 耗时: {elapsed_ms:.2f}ms")

    return timing_hook


class BuiltinHooks:
    """内置 Hooks"""

    @staticmethod
    async def opa_permission_check(context: HookContext, *args, **kwargs) -> bool:
        """OPA 权限校验 Hook"""
        from odap.infra.opa import OPAManager

        user_role = context.get_data("user_role")
        operation = context.get_data("operation")
        resource = context.get_data("resource")

        if not all([user_role, operation, resource]):
            return True

        opa_manager = OPAManager()
        allowed = opa_manager.check_permission(user_role, operation, resource)

        if not allowed:
            logger.warning(f"[OPA Hook] 权限被拒绝: {user_role}/{operation}")
            context.add_error(f"Permission denied: {user_role}/{operation}")

        return allowed

    @staticmethod
    async def audit_logging(context: HookContext, result: Any = None, error: Exception = None):
        """审计日志 Hook"""
        log_entry = {
            "event": context.event_name,
            "agent_id": context.agent_id,
            "mission_id": context.mission_id,
            "timestamp": context.timestamp.isoformat(),
            "errors": context.errors,
            "has_error": error is not None or len(context.errors) > 0,
        }

        if error:
            log_entry["error"] = str(error)

        logger.info(f"[Audit] {context.event_name}: {log_entry}")

    @staticmethod
    async def metrics_collection(context: HookContext, result: Any = None):
        """指标收集 Hook"""
        context.set_data("metrics_executed_at", datetime.now().isoformat())
        logger.debug(f"[Metrics] {context.event_name} 指标已收集")


def register_builtin_hooks():
    """注册内置 Hooks"""
    registry = HookRegistry.get_instance()

    registry.register(
        event="mission.start",
        name="audit_logging",
        handler=BuiltinHooks.audit_logging,
        phase=HookPhase.PRE,
        priority=HookPriority.CRITICAL.value,
        description="任务开始审计",
    )

    registry.register(
        event="mission.complete",
        name="audit_logging",
        handler=BuiltinHooks.audit_logging,
        phase=HookPhase.POST,
        priority=HookPriority.CRITICAL.value,
        description="任务完成审计",
    )

    registry.register(
        event="ooda.*",
        name="timing_hook",
        handler=create_timing_hook(HookPhase.POST, "ooda"),
        phase=HookPhase.POST,
        priority=HookPriority.LOW.value,
        description="OODA 阶段计时",
    )

    logger.info("内置 Hooks 注册完成")