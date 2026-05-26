"""
Skill 基类模块
提供统一的 Skill 抽象接口、输入输出模型和注册机制

设计原则：
- BaseSkill 是可选的渐进式升级，旧式裸函数 handler 仍然兼容
- 所有 SkillOutput 必须包含 success/data/error/skill_name 四个标准字段
- SkillInput 继承 Pydantic BaseModel，提供自动校验
- OPA 权限检查通过 requires_opa_check 声明式标记
- v2 增强功能：热插拔、版本管理、健康监控、SkillExecutor
"""

import time
import uuid
import threading
import importlib
import inspect
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Optional, Dict, Any, List, Type

from pydantic import BaseModel, Field


# ============================================================
# 标准 Input / Output 模型
# ============================================================

class SkillInput(BaseModel):
    """所有 Skill 输入的基类"""
    request_id: str = Field(default_factory=lambda: f"req-{uuid.uuid4().hex[:8]}",
                            description="请求追踪ID")
    timestamp: datetime = Field(default_factory=datetime.now, description="请求时间")


class SkillOutput(BaseModel):
    """所有 Skill 输出的标准信封"""
    success: bool = Field(description="执行是否成功")
    data: Dict[str, Any] = Field(default_factory=dict, description="输出数据")
    error: Optional[str] = Field(default=None, description="错误信息")
    execution_time_ms: float = Field(description="执行耗时(毫秒)")
    skill_name: str = Field(description="技能名称")
    request_id: str = Field(default="", description="请求追踪ID")


class SkillMetadata(BaseModel):
    """Skill 元数据"""
    name: str = Field(description="技能唯一标识")
    description: str = Field(description="技能描述")
    category: str = Field(default="general", description="技能分类: intelligence/operations/analysis/recommendation/visualization/planning/policy/computation/ontology/task_management")
    danger_level: str = Field(default="low", description="危险等级: low/medium/high/critical")
    requires_opa_check: bool = Field(default=False, description="是否需要 OPA 权限校验")
    opa_action: str = Field(default="", description="OPA action 名称 (requires_opa_check=True 时必填)")
    input_schema: Optional[Type[SkillInput]] = Field(default=None, description="输入 Schema 类")
    version: str = Field(default="1.0.0", description="技能版本")


# ============================================================
# BaseSkill 抽象基类
# ============================================================

class BaseSkill(ABC):
    """
    Skill 抽象基类

    所有新 Skill 应继承此类并实现 execute() 方法。
    旧式裸函数 handler 通过 LegacySkillAdapter 适配。

    使用示例::

        class RadarSearchInput(SkillInput):
            region: str = Field(description="搜索区域")
            scan_depth: str = Field(default="normal")

        class RadarSearchSkill(BaseSkill):
            metadata = SkillMetadata(
                name="search_radar",
                description="搜索指定区域的雷达",
                category="intelligence",
            )
            input_schema = RadarSearchInput

            def execute(self, input_data: SkillInput) -> SkillOutput:
                results = self._do_search(input_data.region)
                return SkillOutput(
                    success=True,
                    data={"radars": results},
                    execution_time_ms=0,
                    skill_name=self.metadata.name,
                    request_id=input_data.request_id,
                )
    """

    metadata: SkillMetadata
    input_schema: Optional[Type[SkillInput]] = None

    @abstractmethod
    def execute(self, input_data: SkillInput) -> SkillOutput:
        """
        执行技能（同步）

        Args:
            input_data: 经过校验的输入数据

        Returns:
            标准化输出
        """
        ...

    def validate_input(self, raw_input: Dict[str, Any]) -> SkillInput:
        """
        校验并转换原始输入

        Args:
            raw_input: 原始字典输入

        Returns:
            校验后的 SkillInput 实例

        Raises:
            ValidationError: 输入校验失败
        """
        if self.input_schema is None:
            return SkillInput(**{k: v for k, v in raw_input.items()
                                 if k in SkillInput.model_fields})

        return self.input_schema(**raw_input)

    def run(self, raw_input: Optional[Dict[str, Any]] = None) -> SkillOutput:
        """
        完整执行流程：校验 → 执行 → 计时

        Args:
            raw_input: 原始输入字典，None 时使用空字典

        Returns:
            SkillOutput
        """
        raw_input = raw_input or {}
        start = time.perf_counter()

        try:
            input_data = self.validate_input(raw_input)
            result = self.execute(input_data)
        except Exception as e:
            elapsed = (time.perf_counter() - start) * 1000
            return SkillOutput(
                success=False,
                error=str(e),
                execution_time_ms=elapsed,
                skill_name=self.metadata.name,
                request_id=raw_input.get("request_id", ""),
            )

        if not result.request_id:
            result.request_id = raw_input.get("request_id", "")

        return result


# ============================================================
# LegacySkillAdapter: 兼容旧式裸函数 (DEPRECATED)
# ============================================================

# DEPRECATED: LegacySkillAdapter 仅用于兼容旧式裸函数 handler，
# 新代码应直接继承 BaseSkill 并实现 execute() 方法。

class LegacySkillAdapter(BaseSkill):
    """
    适配器：将旧式裸函数 handler 包装为 BaseSkill

    用于渐进式迁移，不破坏现有 register_skill() 调用链。
    """

    def __init__(self, name: str, description: str, handler,
                 category: str = "legacy", danger_level: str = "low"):
        self._handler = handler
        self.metadata = SkillMetadata(
            name=name,
            description=description,
            category=category,
            danger_level=danger_level,
        )

    def execute(self, input_data: SkillInput) -> SkillOutput:
        """调用原始裸函数"""
        start = time.perf_counter()
        try:
            raw = input_data.model_dump(exclude={"request_id", "timestamp"})
            result = self._handler(**raw)
            elapsed = (time.perf_counter() - start) * 1000

            if isinstance(result, dict):
                data = result
                success = result.get("status", "success") != "error" and result.get("status") != "denied"
                if result.get("status") == "denied":
                    return SkillOutput(
                        success=False,
                        data=result,
                        error=result.get("message", "权限不足"),
                        execution_time_ms=elapsed,
                        skill_name=self.metadata.name,
                        request_id=input_data.request_id,
                    )
            elif isinstance(result, list):
                data = {"items": result}
                success = True
            else:
                data = {"result": result}
                success = True

            return SkillOutput(
                success=success,
                data=data,
                execution_time_ms=elapsed,
                skill_name=self.metadata.name,
                request_id=input_data.request_id,
            )
        except Exception as e:
            elapsed = (time.perf_counter() - start) * 1000
            return SkillOutput(
                success=False,
                error=str(e),
                execution_time_ms=elapsed,
                skill_name=self.metadata.name,
                request_id=input_data.request_id,
            )


# ============================================================
# SkillRegistry: 统一注册表 (DEPRECATED - 请使用 SkillRegistryV2)
# ============================================================

# DEPRECATED: SkillRegistry 是 v1 注册表，新代码应使用 SkillRegistryV2。
# 保留此类以保持向后兼容。

class SkillRegistry:
    """
    统一技能注册表

    同时支持：
    1. BaseSkill 子类注册（新方式）
    2. 裸函数 handler 注册（旧方式，通过 register_skill() 兼容）
    """

    def __init__(self):
        self._skills: Dict[str, BaseSkill] = {}
        self._legacy_catalog: Dict[str, Dict] = {}

    def register(self, skill: BaseSkill):
        """注册 BaseSkill 实例"""
        self._skills[skill.metadata.name] = skill

    def register_legacy(self, name: str, description: str, handler, category: str = "legacy"):
        """
        注册旧式裸函数（兼容 register_skill() 调用）

        同时创建 LegacySkillAdapter 存入 _skills。
        """
        adapter = LegacySkillAdapter(name, description, handler, category=category)
        self._skills[name] = adapter
        self._legacy_catalog[name] = {
            "description": description,
            "handler": handler,
        }

    def get(self, name: str) -> Optional[BaseSkill]:
        """获取 Skill 实例"""
        return self._skills.get(name)

    def get_legacy_handler(self, name: str):
        """获取旧式 handler（向后兼容）"""
        entry = self._legacy_catalog.get(name)
        return entry["handler"] if entry else None

    def list_skills(self) -> List[Dict[str, str]]:
        """列出所有已注册 Skill 的元数据"""
        return [
            {
                "name": s.metadata.name,
                "description": s.metadata.description,
                "category": s.metadata.category,
                "danger_level": s.metadata.danger_level,
                "version": s.metadata.version,
            }
            for s in self._skills.values()
        ]

    def __contains__(self, name: str) -> bool:
        return name in self._skills

    def __len__(self) -> int:
        return len(self._skills)


# 全局注册表单例
_registry = SkillRegistry()


def get_registry() -> SkillRegistry:
    """获取全局 SkillRegistry 实例"""
    return _registry


# ============================================================
# v2 增强功能：状态枚举、版本管理、健康监控、热插拔、执行器
# ============================================================

class SkillStatus(Enum):
    """Skill 状态"""
    REGISTERED = "registered"
    LOADING = "loading"
    READY = "ready"
    RUNNING = "running"
    DISABLED = "disabled"
    FAILED = "failed"
    UNLOADED = "unloaded"


class HealthStatus(str, Enum):
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

    def __init__(self, hot_swapper: SkillHotSwapper, opa_manager=None):
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

        danger_level = skill_reg.skill.metadata.danger_level
        if danger_level in ("high", "critical") and not self._confirm_dangerous_action(skill_name, danger_level, user):
            skill_reg.health_info.failed_calls += 1
            return SkillOutput(
                success=False,
                error=f"Action requires confirmation: {skill_name} (danger_level={danger_level})",
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

    def _confirm_dangerous_action(self, skill_name: str, danger_level: str, user: Dict = None) -> bool:
        """检查高危操作是否已确认"""
        if user and user.get("role") == "admin":
            return True
        if user and user.get("confirmed_actions") and skill_name in user.get("confirmed_actions", []):
            return True
        if danger_level == "critical":
            return False
        if danger_level == "high":
            return user is not None and user.get("role") in ("commander", "admin")
        return True


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
