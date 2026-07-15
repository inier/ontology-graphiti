"""
ServitizationSkillAdapter — 服务化引擎的 Skill 包装。

包装 ServitizationService 的 list_services / get_service 方法。
"""
import logging
import time
from typing import Any, Optional

from pydantic import Field
from odap.tools.base import SkillInput, SkillOutput

from odap.biz.core.ontology.application.ontology_app_skill import OntologyAppSkill

logger = logging.getLogger(__name__)


class ServitizationSkillInput(SkillInput):
    action: str = Field(default="list_services")
    status: Optional[str] = Field(default=None)
    service_id: Optional[str] = Field(default=None)


class ServitizationSkillAdapter(OntologyAppSkill):
    """服务化引擎 skill 包装。"""
    input_schema = ServitizationSkillInput

    def __init__(
        self,
        workspace_id: str,
        ontology_id: str,
        name: str = "ontology_servitization_skill",
        description: str = "包装 ServitizationService，提供服务目录查询/发布能力。",
    ) -> None:
        super().__init__(
            name=name,
            description=description,
            workspace_id=workspace_id,
            ontology_id=ontology_id,
            danger_level="medium",
            engine_name="servitization",
        )

    def bind_engine(self, engine: Any) -> None:
        if not hasattr(engine, "list_services") or not hasattr(engine, "get_service"):
            raise TypeError(
                f"Engine {type(engine).__name__} 缺少 list_services / get_service 方法"
            )
        self._engine = engine
        self._bound = True

    def execute(self, input_data: SkillInput) -> SkillOutput:
        start = time.perf_counter()
        validated: ServitizationSkillInput = self.validate_input(input_data.model_dump())
        action = validated.action
        try:
            if action == "list_services":
                result = self.engine.list_services(status=validated.status)
            elif action == "get_service":
                if not validated.service_id:
                    raise ValueError("get_service 需要 service_id")
                result = self.engine.get_service(validated.service_id)
            else:
                raise ValueError(f"Unknown servitization action: {action}")

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


__all__ = ["ServitizationSkillAdapter", "ServitizationSkillInput"]
