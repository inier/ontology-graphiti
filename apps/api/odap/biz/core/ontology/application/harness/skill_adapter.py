"""
HarnessSkillAdapter — 蓝图/会话引擎的 Skill 包装。

包装 HarnessService 的 list_sessions / create_session 方法。
"""
import logging
import time
from typing import Any, Optional

from pydantic import Field
from odap.tools.base import SkillInput, SkillOutput

from odap.biz.core.ontology.application.ontology_app_skill import OntologyAppSkill

logger = logging.getLogger(__name__)


class HarnessSkillInput(SkillInput):
    action: str = Field(default="list_sessions")
    status: Optional[str] = Field(default=None)
    session_name: Optional[str] = Field(default=None)
    description: Optional[str] = Field(default=None)
    requirement: Optional[str] = Field(default=None)


class HarnessSkillAdapter(OntologyAppSkill):
    """蓝图/会话引擎 skill 包装。"""
    input_schema = HarnessSkillInput

    def __init__(
        self,
        workspace_id: str,
        ontology_id: str,
        name: str = "ontology_harness_skill",
        description: str = "包装 HarnessService，提供 session 创建/推进能力。",
    ) -> None:
        super().__init__(
            name=name,
            description=description,
            workspace_id=workspace_id,
            ontology_id=ontology_id,
            danger_level="low",
            engine_name="harness",
        )

    def bind_engine(self, engine: Any) -> None:
        if not hasattr(engine, "list_sessions") or not hasattr(engine, "create_session"):
            raise TypeError(
                f"Engine {type(engine).__name__} 缺少 list_sessions / create_session 方法"
            )
        self._engine = engine
        self._bound = True

    def execute(self, input_data: SkillInput) -> SkillOutput:
        start = time.perf_counter()
        validated: HarnessSkillInput = self.validate_input(input_data.model_dump())
        action = validated.action
        ctx = self._resolve_ctx(validated)
        try:
            if action == "list_sessions":
                result = self.engine.list_sessions(status=validated.status)
            elif action == "create_session":
                name = validated.session_name or "untitled"
                result = self.engine.create_session(
                    name=name,
                    description=validated.description or "",
                    requirement=validated.requirement or "",
                    workspace_id=ctx["workspace_id"],
                    scenario_id=ctx.get("ontology_id"),
                )
            else:
                raise ValueError(f"Unknown harness action: {action}")

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


__all__ = ["HarnessSkillAdapter", "HarnessSkillInput"]
