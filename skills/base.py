"""
Skill 基类模块
提供统一的 Skill 抽象接口、输入输出模型和注册机制

设计原则：
- BaseSkill 是可选的渐进式升级，旧式裸函数 handler 仍然兼容
- 所有 SkillOutput 必须包含 success/data/error/skill_name 四个标准字段
- SkillInput 继承 Pydantic BaseModel，提供自动校验
- OPA 权限检查通过 requires_opa_check 声明式标记
"""

import time
import uuid
from abc import ABC, abstractmethod
from datetime import datetime
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
            # 无 schema 时使用基类 SkillInput
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

        # 确保输出包含 request_id
        if not result.request_id:
            result.request_id = raw_input.get("request_id", "")

        return result


# ============================================================
# LegacySkillAdapter: 兼容旧式裸函数
# ============================================================

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
            # 旧函数直接接收 **kwargs
            raw = input_data.model_dump(exclude={"request_id", "timestamp"})
            result = self._handler(**raw)
            elapsed = (time.perf_counter() - start) * 1000

            # 兼容：旧函数可能返回 dict 或 list
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
# SkillRegistry: 统一注册表
# ============================================================

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
