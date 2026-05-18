"""
Skill 基础设施 v2 - BaseSkill 增强版
支持热插拔、版本管理、健康监控和 SkillExecutor

功能：
- BaseSkill v2 - 增强的 Skill 基类
- Skill 热插拔（动态加载/卸载）
- Skill 版本管理
- Skill 健康监控
- SkillExecutor - OPA 桥接执行器
"""

import sys
import os
import json
import time
import threading
import importlib
import inspect
from typing import Dict, Any, List, Optional, Type, Callable
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from tools.base import BaseSkill, SkillInput, SkillOutput, SkillMetadata, SkillRegistry, get_registry

try:
    from odap.infra.opa.opa_service_v2 import OPAManagerV2
    OPA_AVAILABLE = True
except ImportError:
    OPAManagerV2 = None
    OPA_AVAILABLE = False


class SkillStatus(Enum):
    """Skill 状态"""
    REGISTERED = "registered"
    LOADING = "loading"
    READY = "ready"
    RUNNING = "running"
    DISABLED = "disabled"
    FAILED = "failed"
    UNLOADED = "unloaded"


class HealthStatus(Enum):
    """健康状态"""
    HEALTHY = "healthy"
    DEGRADED = "degraded"
    UNHEALTHY = "unhealthy"


@dataclass
class SkillVersion:
    """Skill 版本信息"""
    version: str
    loaded_at: str
    changelog: str = ""
    is_active: bool = True


@dataclass
class SkillHealthInfo:
    """Skill 健康信息"""
    name: str
    status: str
    health: str
    registered_at: str = ""
    last_modified: str = ""
    total_calls: int = 0
    success_calls: int = 0
    failed_calls: int = 0
    avg_execution_time_ms: float = 0
    last_execution_time: Optional[str] = None
    last_error: Optional[str] = None


@dataclass
class SkillRegistration:
    """Skill 注册信息"""
    skill: BaseSkill
    status: SkillStatus
    health_info: SkillHealthInfo
    versions: List[SkillVersion] = field(default_factory=list)
    dependencies: List[str] = field(default_factory=list)
    loaded_by: Optional[str] = None


class SkillHotSwapper:
    """Skill 热插拔管理器"""

    def __init__(self, registry: SkillRegistry):
        self.registry = registry
        self._skills: Dict[str, SkillRegistration] = {}
        self._lock = threading.RLock()

    def register(self, skill: BaseSkill, version: str = "1.0.0",
                 changelog: str = "", dependencies: List[str] = None) -> bool:
        """注册 Skill（支持热插拔）"""
        with self._lock:
            name = skill.metadata.name

            if name in self._skills:
                return self._update_version(name, version, changelog)

            health_info = SkillHealthInfo(
                name=name,
                status=SkillStatus.READY.value,
                health=HealthStatus.HEALTHY.value,
                registered_at=datetime.now(timezone.utc).isoformat(),
                last_modified=datetime.now(timezone.utc).isoformat()
            )

            registration = SkillRegistration(
                skill=skill,
                status=SkillStatus.READY,
                health_info=health_info,
                versions=[SkillVersion(version=version, loaded_at=datetime.now(timezone.utc).isoformat(), changelog=changelog)],
                dependencies=dependencies or []
            )

            self._skills[name] = registration
            self.registry.register(skill)
            return True

    def _update_version(self, name: str, version: str, changelog: str) -> bool:
        """更新 Skill 版本"""
        reg = self._skills[name]
        reg.versions.append(SkillVersion(
            version=version,
            loaded_at=datetime.now(timezone.utc).isoformat(),
            changelog=changelog,
            is_active=True
        ))

        for v in reg.versions[:-1]:
            v.is_active = False

        reg.health_info.last_modified = datetime.now(timezone.utc).isoformat()
        return True

    def unregister(self, name: str, force: bool = False) -> bool:
        """卸载 Skill"""
        with self._lock:
            if name not in self._skills:
                return False

            reg = self._skills[name]
            if reg.health_info.total_calls > 0 and not force:
                return False

            reg.status = SkillStatus.UNLOADED
            return True

    def enable(self, name: str) -> bool:
        """启用 Skill"""
        with self._lock:
            if name not in self._skills:
                return False
            reg = self._skills[name]
            reg.status = SkillStatus.READY
            reg.health_info.status = SkillStatus.READY.value
            return True

    def disable(self, name: str) -> bool:
        """禁用 Skill"""
        with self._lock:
            if name not in self._skills:
                return False
            reg = self._skills[name]
            reg.status = SkillStatus.DISABLED
            reg.health_info.status = SkillStatus.DISABLED.value
            return True

    def get_health_info(self, name: str) -> Optional[SkillHealthInfo]:
        """获取健康信息"""
        reg = self._skills.get(name)
        return reg.health_info if reg else None

    def list_all_health(self) -> List[SkillHealthInfo]:
        """列出所有 Skill 健康状态"""
        return [reg.health_info for reg in self._skills.values()]


class SkillExecutorV2:
    """
    Skill 执行器 v2
    支持 OPA 权限桥接、健康监控、重试机制
    """

    def __init__(self, hot_swapper: SkillHotSwapper, opa_manager: OPAManagerV2 = None):
        self.hot_swapper = hot_swapper
        self.opa_manager = opa_manager
        self._retry_attempts = 3
        self._retry_delay_ms = 100

    def execute(self, skill_name: str, input_data: Dict,
               user: Dict = None, retry: bool = True) -> SkillOutput:
        """
        执行 Skill

        Args:
            skill_name: Skill 名称
            input_data: 输入数据
            user: 用户信息（用于 OPA 权限检查）
            retry: 是否启用重试

        Returns:
            SkillOutput
        """
        skill_reg = self.hot_swapper._skills.get(skill_name)
        if not skill_reg:
            return SkillOutput(
                success=False,
                error=f"Skill not found: {skill_name}",
                execution_time_ms=0,
                skill_name=skill_name
            )

        if skill_reg.status == SkillStatus.DISABLED:
            return SkillOutput(
                success=False,
                error=f"Skill is disabled: {skill_name}",
                execution_time_ms=0,
                skill_name=skill_name
            )

        if skill_reg.skill.metadata.requires_opa_check and self.opa_manager and user:
            if not self._check_opa_permission(skill_name, user):
                skill_reg.health_info.failed_calls += 1
                return SkillOutput(
                    success=False,
                    error="Permission denied",
                    execution_time_ms=0,
                    skill_name=skill_name
                )

        start_time = time.perf_counter()
        attempt = 0
        last_error = None

        while attempt < (self._retry_attempts if retry else 1):
            try:
                skill_reg.status = SkillStatus.RUNNING
                result = skill_reg.skill.run(input_data)
                skill_reg.health_info.total_calls += 1

                if result.success:
                    skill_reg.health_info.success_calls += 1
                else:
                    skill_reg.health_info.failed_calls += 1
                    last_error = result.error

                skill_reg.health_info.last_execution_time = datetime.now(timezone.utc).isoformat()
                skill_reg.health_info.last_error = last_error

                elapsed = (time.perf_counter() - start_time) * 1000
                skill_reg.health_info.avg_execution_time_ms = (
                    (skill_reg.health_info.avg_execution_time_ms * (skill_reg.health_info.total_calls - 1) + elapsed)
                    / skill_reg.health_info.total_calls
                )

                skill_reg.status = SkillStatus.READY
                return result

            except Exception as e:
                last_error = str(e)
                attempt += 1
                if attempt < self._retry_attempts:
                    time.sleep(self._retry_delay_ms / 1000)

        skill_reg.health_info.total_calls += 1
        skill_reg.health_info.failed_calls += 1
        skill_reg.health_info.last_error = last_error
        skill_reg.status = SkillStatus.READY

        return SkillOutput(
            success=False,
            error=f"Failed after {self._retry_attempts} attempts: {last_error}",
            execution_time_ms=(time.perf_counter() - start_time) * 1000,
            skill_name=skill_name
        )

    def _check_opa_permission(self, skill_name: str, user: Dict) -> bool:
        """检查 OPA 权限"""
        if not self.opa_manager:
            return True

        skill_reg = self.hot_swapper._skills.get(skill_name)
        if not skill_reg:
            return False

        action = skill_reg.skill.metadata.opa_action
        if not action:
            return True

        user_role = user.get("role", "guest")
        result = self.opa_manager.check_permission(
            user_role, action, {"type": "skill", "id": skill_name}
        )
        return result


class SkillRegistryV2:
    """
    Skill 注册表 v2
    集成热插拔、版本管理、健康监控
    """

    def __init__(self):
        self._registry = get_registry()
        self._hot_swapper = SkillHotSwapper(self._registry)
        self._executor = SkillExecutorV2(self._hot_swapper)
        self._skill_modules: Dict[str, str] = {}

    def register(self, skill: BaseSkill, version: str = "1.0.0",
                changelog: str = "", dependencies: List[str] = None) -> bool:
        """注册 Skill"""
        return self._hot_swapper.register(skill, version, changelog, dependencies)

    def register_module(self, module_path: str) -> int:
        """
        动态加载模块中的所有 Skill

        Args:
            module_path: 模块路径，如 'odap.tools.built_in'

        Returns:
            加载的 Skill 数量
        """
        try:
            module = importlib.import_module(module_path)
            loaded = 0

            for name, obj in inspect.getmembers(module):
                if inspect.isclass(obj) and issubclass(obj, BaseSkill) and obj != BaseSkill:
                    try:
                        skill_instance = obj()
                        self.register(skill_instance)
                        loaded += 1
                    except Exception as e:
                        print(f"Failed to instantiate Skill {name}: {e}")

            self._skill_modules[module_path] = module
            return loaded
        except Exception as e:
            print(f"Failed to load module {module_path}: {e}")
            return 0

    def unregister(self, name: str, force: bool = False) -> bool:
        """卸载 Skill"""
        return self._hot_swapper.unregister(name, force)

    def execute(self, skill_name: str, input_data: Dict,
               user: Dict = None) -> SkillOutput:
        """执行 Skill"""
        return self._executor.execute(skill_name, input_data, user)

    def discover(self, pattern: str = None) -> List[Dict[str, Any]]:
        """
        发现 Skill

        Args:
            pattern: 搜索模式（支持前缀匹配）

        Returns:
            Skill 列表
        """
        skills = self._registry.list_skills()

        if pattern:
            skills = [s for s in skills if pattern.lower() in s["name"].lower()]

        for skill in skills:
            health = self._hot_swapper.get_health_info(skill["name"])
            if health:
                skill["health"] = health.health
                skill["status"] = health.status
                skill["total_calls"] = health.total_calls
                skill["success_rate"] = (
                    health.success_calls / health.total_calls * 100
                    if health.total_calls > 0 else 0
                )

        return skills

    def get_health_report(self) -> Dict[str, Any]:
        """获取健康报告"""
        health_list = self._hot_swapper.list_all_health()

        healthy = sum(1 for h in health_list if h.health == HealthStatus.HEALTHY.value)
        degraded = sum(1 for h in health_list if h.health == HealthStatus.DEGRADED.value)
        unhealthy = sum(1 for h in health_list if h.health == HealthStatus.UNHEALTHY.value)

        total_calls = sum(h.total_calls for h in health_list)
        total_success = sum(h.success_calls for h in health_list)
        total_failed = sum(h.failed_calls for h in health_list)

        return {
            "total_skills": len(health_list),
            "healthy_count": healthy,
            "degraded_count": degraded,
            "unhealthy_count": unhealthy,
            "total_calls": total_calls,
            "total_success": total_success,
            "total_failed": total_failed,
            "overall_success_rate": (total_success / total_calls * 100) if total_calls > 0 else 0,
            "skills": health_list
        }

    def get_executor(self) -> SkillExecutorV2:
        """获取执行器"""
        return self._executor


_global_registry_v2: Optional[SkillRegistryV2] = None


def get_registry_v2() -> SkillRegistryV2:
    """获取全局 SkillRegistryV2 实例"""
    global _global_registry_v2
    if _global_registry_v2 is None:
        _global_registry_v2 = SkillRegistryV2()
    return _global_registry_v2


if __name__ == "__main__":
    registry = get_registry_v2()

    print("Skill 基础设施 v2 初始化完成")

    print("\n测试 Skill 注册:")
    class TestSkillInput(SkillInput):
        value: int = Field(default=0)

    class TestSkill(BaseSkill):
        metadata = SkillMetadata(
            name="test_skill",
            description="测试 Skill",
            category="test",
        )
        input_schema = TestSkillInput

        def execute(self, input_data: SkillInput) -> SkillOutput:
            return SkillOutput(
                success=True,
                data={"result": input_data.value * 2},
                execution_time_ms=0,
                skill_name=self.metadata.name,
                request_id=input_data.request_id
            )

    registry.register(TestSkill(), version="1.0.0", changelog="初始版本")

    print("  注册 Skill: test_skill")

    print("\n测试 Skill 执行:")
    result = registry.execute("test_skill", {"value": 21})
    print(f"  执行结果: {result.success}")
    print(f"  输出数据: {result.data}")

    print("\n测试 Skill 发现:")
    skills = registry.discover("test")
    print(f"  发现 {len(skills)} 个 Skill")

    print("\n测试健康报告:")
    report = registry.get_health_report()
    print(f"  总 Skill 数: {report['total_skills']}")
    print(f"  健康数: {report['healthy_count']}")
    print(f"  总调用数: {report['total_calls']}")
