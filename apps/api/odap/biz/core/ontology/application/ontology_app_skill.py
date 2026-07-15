"""
OntologyAppSkill — 本体应用引擎的 Skill 包装接口。

本模块为「本体应用层」4 大引擎（runtime / servitization / team_agent / harness）
提供统一的 Skill 协议，使原生硬编码引擎能同时被 skill 调度器发现和执行。

设计原则：
- 零侵入：原生引擎代码 0 改动
- 包装式：仅将 engine.method 包装为 BaseSkill.execute
- 上下文强制：所有 skill 必须绑定 workspace_id + ontology_id
- 失败安全：engine.bind() 失败时仅 warn，不阻塞其他 skill 注册
"""
import logging
from abc import abstractmethod
from typing import Any, ClassVar, Dict, Optional

from odap.tools.base import BaseSkill, SkillInput, SkillMetadata, SkillOutput

logger = logging.getLogger(__name__)


class OntologyAppSkill(BaseSkill):
    """
    本体应用 skill 抽象基类。

    子类必须：
    1. 设置 metadata.category = "ontology_app"
    2. 实现 bind_engine() 绑定原生引擎实例
    3. 实现 execute() 委托到原生引擎
    """

    CATEGORY: ClassVar[str] = "ontology_app"

    workspace_id: Optional[str] = None
    ontology_id: Optional[str] = None

    def __init__(
        self,
        name: str,
        description: str,
        workspace_id: str,
        ontology_id: str,
        danger_level: str = "medium",
        engine_name: str = "",
    ) -> None:
        self.metadata = SkillMetadata(
            name=name,
            description=description,
            category=self.CATEGORY,
            danger_level=danger_level,
        )
        self.workspace_id = workspace_id
        self.ontology_id = ontology_id
        self._engine_name = engine_name or name
        self._engine: Optional[Any] = None
        self._bound: bool = False

    @abstractmethod
    def bind_engine(self, engine: Any) -> None:
        """绑定原生引擎实例。子类可在此校验引擎接口。"""

    @property
    def engine(self) -> Any:
        if not self._bound or self._engine is None:
            raise RuntimeError(
                f"Engine '{self._engine_name}' not bound for skill '{self.metadata.name}'"
            )
        return self._engine

    def _resolve_ctx(self, input_data: SkillInput) -> Dict[str, Any]:
        """从 input 提取 workspace/ontology，允许覆盖实例默认上下文。"""
        return {
            "workspace_id": getattr(input_data, "workspace_id", None) or self.workspace_id,
            "ontology_id": getattr(input_data, "ontology_id", None) or self.ontology_id,
            "request_id": input_data.request_id,
        }

    def _make_output(
        self,
        success: bool,
        data: Dict[str, Any],
        error: Optional[str] = None,
        elapsed_ms: float = 0.0,
        input_data: Optional[SkillInput] = None,
    ) -> SkillOutput:
        return SkillOutput(
            success=success,
            data=data,
            error=error,
            execution_time_ms=elapsed_ms,
            skill_name=self.metadata.name,
            request_id=input_data.request_id if input_data else "",
        )


__all__ = ["OntologyAppSkill"]
