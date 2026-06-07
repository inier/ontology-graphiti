"""
RuntimeSkillAdapter — 运行时引擎的 Skill 包装。

包装 OntologyRuntimeService 的 list_functions / execute_function 方法。
原生 engine 代码 0 改动。
"""
import logging
import time
from typing import Any, Optional

from pydantic import Field
from odap.tools.base import BaseSkill, SkillInput, SkillOutput

from odap.biz.core.ontology.application.ontology_app_skill import OntologyAppSkill

logger = logging.getLogger(__name__)


class RuntimeSkillInput(SkillInput):
    """RuntimeSkillAdapter 输入。"""
    action: str = Field(default="list_functions")
    function_type: Optional[str] = Field(default=None)
    target_object_type: Optional[str] = Field(default=None)
    function_id: Optional[str] = Field(default=None)
    context: Optional[dict] = Field(default=None)


class RuntimeSkillAdapter(OntologyAppSkill):
    """运行时引擎 skill 包装。"""
    input_schema = RuntimeSkillInput

    def __init__(
        self,
        workspace_id: str,
        ontology_id: str,
        name: str = "ontology_runtime_skill",
        description: str = "包装 OntologyRuntimeService，提供 function 注册/执行能力。",
    ) -> None:
        super().__init__(
            name=name,
            description=description,
            workspace_id=workspace_id,
            ontology_id=ontology_id,
            danger_level="medium",
            engine_name="runtime",
        )

    def bind_engine(self, engine: Any) -> None:
        if not hasattr(engine, "list_functions") or not hasattr(engine, "execute_function"):
            raise TypeError(
                f"Engine {type(engine).__name__} 缺少 list_functions / execute_function 方法"
            )
        self._engine = engine
        self._bound = True

    def execute(self, input_data: SkillInput) -> SkillOutput:
        start = time.perf_counter()
        validated: RuntimeSkillInput = self.validate_input(input_data.model_dump())
        action = validated.action
        ctx = self._resolve_ctx(validated)
        try:
            if action == "list_functions":
                result = self.engine.list_functions(
                    function_type=validated.function_type,
                    target_object_type=validated.target_object_type,
                )
            elif action == "execute_function":
                if not validated.function_id:
                    raise ValueError("execute_function 需要 function_id")
                fn_ctx = dict(validated.context or {})
                fn_ctx.update(ctx)
                result = self.engine.execute_function(validated.function_id, fn_ctx)
            else:
                raise ValueError(f"Unknown runtime action: {action}")

            elapsed = (time.perf_counter() - start) * 1000
            return self._make_output(
                success=result.get("status", "success") != "error",
                data=result,
                elapsed_ms=elapsed,
                input_data=validated,
            )
        except Exception as e:
            elapsed = (time.perf_counter() - start) * 1000
            return self._make_output(
                success=False, data={}, error=str(e), elapsed_ms=elapsed, input_data=validated,
            )


__all__ = ["RuntimeSkillAdapter", "RuntimeSkillInput"]
